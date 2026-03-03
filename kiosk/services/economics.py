
import requests
import logging
import traceback
from ..config import Config
from ..database import get_db_connection
import psycopg

logger = logging.getLogger(__name__)

class EconomicsService:
    @staticmethod
    def _get_headers(idempotency_key=None):
        headers = {
            'Content-Type': 'application/json',
            'X-AgreementGrantToken': Config.ECO_GRANT_TOKEN,
            'X-AppSecretToken': Config.ECO_SECRET_TOKEN
        }
        if idempotency_key:
            headers['Idempotency-Key'] = str(idempotency_key)
        return headers

    @staticmethod
    def _request(method, url, data=None, key=None):
        headers = EconomicsService._get_headers(key)
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, timeout=5)
                logger.debug(f"Getting from {url}")
            elif method == 'POST':
                response = requests.post(url, headers=headers, json=data, timeout=5)
                logger.debug(f"Posting to {url}")
            elif method == 'PUT':
                response = requests.put(url, headers=headers, json=data, timeout=5)
                logger.debug(f"Putting to {url}")
            
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            logger.error(f"Economics API Error ({method} {url}): {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"Economics Request Failed ({method} {url}): {e}")
            raise

    @staticmethod
    def update_users():
        groups = ','.join(str(g) for g in Config.CUSTOMER_GROUPS_ALL)
        url = f"https://restapi.e-conomic.com/customers?pagesize=1000&filter=barred$eq:False$and:customerGroup.customerGroupNumber$in:[{groups}]"
        
        api_ids = set()
        upsert_list = []

        while url:
            try:
                data = EconomicsService._request('GET', url)
            except Exception as e:
                logger.error(f"Failed to fetch users from Economics API: {e}")
                raise

            if 'collection' in data:
                for restitem in data['collection']:
                    api_ids.add(restitem['customerNumber'])
                    upsert_list.append((
                        restitem['customerNumber'], 
                        restitem['name'], 
                        restitem['customerGroup']['customerGroupNumber']
                    ))
            
            url = data.get('pagination', {}).get('nextPage')

        try:
            with get_db_connection() as conn:
                with conn.transaction():
                    with conn.cursor(row_factory=psycopg.rows.dict_row) as curs:
                        # Find users to delete
                        curs.execute("SELECT customerid FROM customers WHERE deleted = false")
                        db_users = curs.fetchall()
                        
                        delete_list = []
                        for user in db_users:
                            if user['customerid'] not in api_ids:
                                delete_list.append((user['customerid'],))
                        
                        if delete_list:
                            curs.executemany("UPDATE customers SET deleted = true WHERE customerid = %s", delete_list)

                        if upsert_list:
                            curs.executemany("""
                                INSERT INTO customers (customerid, customername, customergroup) 
                                VALUES (%s, %s, %s) 
                                ON CONFLICT (customerid) 
                                DO UPDATE SET customername = EXCLUDED.customername, deleted = false, customergroup = EXCLUDED.customergroup
                            """, upsert_list)
        except Exception as e:
            logger.error(f"Database error during ecoUpdateUsers: {e}")

    @staticmethod
    def find_kiosk_draft_line(customerid, product_id, sold_product_name, sold_item_price):
        """
        Returns (draft_id, line_id) if found
        Returns (last_seen_draft_id, None) if not found but drafts exist
        Returns (None, None) if no drafts exist
        """
        url = f"https://restapi.e-conomic.com/orders/drafts?filter=customer.customernumber$eq:{customerid}"
        
        try:
            response = EconomicsService._request('GET', url)
        except Exception:
            return None, None
        
        found_draft_id = None
        
        if 'collection' in response:
            for draft in response['collection']: 
                draft_url = draft['self']
                try:
                    draft_response = EconomicsService._request('GET', draft_url)
                except Exception:
                    continue
                
                current_draft_id = draft_response['orderNumber']
                
                if 'lines' in draft_response:
                    for line in draft_response['lines']:
                        p_info = line.get('product')
                        if (p_info and 
                            str(p_info.get('productNumber')) == str(product_id) and 
                            line.get('description') == str(sold_product_name) and 
                            round(float(line.get('unitNetPrice')), 2) == round(float(sold_item_price), 2)):
                            
                            return current_draft_id, line['lineNumber']
                
                found_draft_id = current_draft_id

        return found_draft_id, None

    @staticmethod
    def create_empty_order(customerid, salesid):
        url_template = f"https://restapi.e-conomic.com/customers/{customerid}/templates/invoice"
        template_data = EconomicsService._request('GET', url_template)
        
        url_create = "https://restapi.e-conomic.com/orders/drafts"
        idem_key = f"create-inv-{salesid}"
        new_draft = EconomicsService._request('POST', url_create, data=template_data, key=idem_key)
        
        return new_draft['orderNumber']

    @staticmethod
    def create_draft_order_line(customerid, order_draft, product_id, sold_product_name, sold_item_price, quantity, salesid):
        url_line_template = f"https://restapi.e-conomic.com/customers/{customerid}/templates/invoiceline/{product_id}"
        order_line = EconomicsService._request('GET', url_line_template)
        
        order_line['quantity'] = quantity
        order_line['description'] = sold_product_name
        order_line['unitNetPrice'] = sold_item_price
        
        url_draft = f"https://restapi.e-conomic.com/orders/drafts/{order_draft}"
        temp_draft = EconomicsService._request('GET', url_draft)
        
        if 'lines' not in temp_draft:
            temp_draft['lines'] = []

        temp_draft['lines'].append(order_line)

        idem_key = f"add-line-{salesid}"
        EconomicsService._request('PUT', url_draft, data=temp_draft, key=idem_key)

    @staticmethod
    def update_sale(order_draft, order_line, value_added, salesid):
        url_draft = f"https://restapi.e-conomic.com/orders/drafts/{order_draft}"
        draft = EconomicsService._request('GET', url_draft)
        pre_update_sum = 0
        
        line_found = False
        if 'lines' in draft:
            for line in draft['lines']:
                if line['lineNumber'] == order_line:
                    pre_update_sum = line['totalNetAmount']
                    line['quantity'] += float(value_added)
                    line_found = True
                    break
        
        if not line_found:
            raise Exception(f"Order line {order_line} not found in draft {order_draft}")
        
        idem_key = f"upd-qty-{salesid}"
        EconomicsService._request('PUT', url_draft, data=draft, key=idem_key)
        
        return pre_update_sum

    @staticmethod
    def sync_pending_transfers():
        # Try to acquire Advisory Lock (ID: 8675309 is arbitrary but constant for this job)
        lock_id = 8675309
        
        try:
            # We need a dedicated connection for the lock that stays open
            # pool.connection() returns a ContextManager, so we must use 'with' to get the actual connection
            with get_db_connection() as lock_conn:
                lock_conn.autocommit = True 
                
                # Try to acquire the lock
                with lock_conn.cursor() as curs:
                    curs.execute("SELECT pg_try_advisory_lock(%s)", (lock_id,))
                    locked = curs.fetchone()[0]
                
                if not locked:
                    logger.info("Another instance is running sync_pending_transfers. Skipping.")
                    return
                
                # Lock acquired, proceed with logic
                try:
                    # Original Logic Starts Here
                    with get_db_connection() as conn:
                        with conn.cursor(row_factory=psycopg.rows.dict_row) as curs:
                            curs.execute("SELECT * FROM ecotransfer JOIN sales on sales.id = ecotransfer.salesid JOIN products on products.productid = sales.productid WHERE transferred = false AND attempts < %s ORDER BY salesid ASC",(Config.ECO_MAX_ATTEMPTS,))
                            waiting_transfers = curs.fetchall()
                    
                    if waiting_transfers:
                        logger.info(f"Sync: {len(waiting_transfers)} pending transfer(s) to process.")

                    synced_count = 0
                    for sale in waiting_transfers:
                        error_msg = None
                        pre_update_sum = None
                        success = False
                        increment_attempts = True
                        safe_price = float(sale['solditemprice'])
                        eco_product_id = Config.ECO_PRODUCT_ID

                        try:
                            # Note: These calls make their own HTTP requests, no DB involvement
                            draft_status = EconomicsService.find_kiosk_draft_line(sale['customerid'], eco_product_id, sale['soldproductname'], safe_price)
                            
                            draft_id = draft_status[0]
                            line_id = draft_status[1]

                            if draft_id is None:
                                draft_id = EconomicsService.create_empty_order(sale['customerid'], sale['salesid'])
                                line_id = None
                            
                            if line_id is None:
                                EconomicsService.create_draft_order_line(sale['customerid'], draft_id, eco_product_id, sale['soldproductname'], safe_price, sale['quantity'], sale['salesid'])
                                pre_update_sum = 0
                            else:
                                pre_update_sum = EconomicsService.update_sale(draft_id, line_id, sale['quantity'], sale['salesid'])
                            
                            success = True
                            synced_count += 1
                            logger.info(f"Successfully synced sale {sale['salesid']} (customer {sale['customerid']}, {sale['soldproductname']})")

                        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as net_e:
                            tb = traceback.extract_tb(net_e.__traceback__)
                            lineno = tb[-1].lineno if tb else 'Unknown'
                            error_msg = f"Network/Timeout: {str(net_e)} (Line: {lineno})"
                            increment_attempts = False
                            logger.warning(f"Network error syncing sale {sale['salesid']}. Will retry. (Line: {lineno})")

                        except requests.exceptions.HTTPError as http_e:
                            tb = traceback.extract_tb(http_e.__traceback__)
                            lineno = tb[-1].lineno if tb else 'Unknown'
                            error_msg = f"API Rejected Sale: {str(http_e)} (Line: {lineno})"
                            increment_attempts = True
                            logger.error(f"Economics API rejected sale {sale['salesid']}: {http_e} (Line: {lineno})")

                        except Exception as e:
                            tb = traceback.extract_tb(e.__traceback__)
                            lineno = tb[-1].lineno if tb else 'Unknown'
                            error_msg = f"General Error: {str(e)} (Line: {lineno})"
                            increment_attempts = True
                            logger.error(f"General error syncing sale {sale['salesid']}: {e} (Line: {lineno})")

                        # Update DB (using separate short-lived connection)
                        try:
                            with get_db_connection() as conn:
                                with conn.cursor() as curs:
                                    if success:
                                        curs.execute("""
                                            UPDATE ecotransfer 
                                            SET timestamp=now(), preupdatesum=%s, attempts=attempts + 1, transferred=true 
                                            WHERE salesid = %s
                                        """, (pre_update_sum, sale['salesid']))
                                    else:
                                        attempt_increment = 1 if increment_attempts else 0
                                        curs.execute("""
                                            UPDATE ecotransfer 
                                            SET timestamp=now(), attempts=attempts + %s, errormsg=%s 
                                            WHERE salesid = %s
                                        """, (attempt_increment, error_msg, sale['salesid']))
                        except Exception as db_e:
                            logger.error(f"Failed to save status for sale {sale['salesid']}: {db_e}")

                    if synced_count > 0:
                        logger.info(f"Sync complete: {synced_count}/{len(waiting_transfers)} transfer(s) succeeded.")

                except Exception as e:
                    logger.error(f"Critical error in sync loop: {e}")

                finally:
                    # Release Lock explicitly before connection closes/returns
                    try:
                        with lock_conn.cursor() as curs:
                            curs.execute("SELECT pg_advisory_unlock(%s)", (lock_id,))
                    except Exception as e:
                        logger.error(f"Failed to release lock: {e}")
                        
        except Exception as e:
            logger.error(f"Locking connection error: {e}")
