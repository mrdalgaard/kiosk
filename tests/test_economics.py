import pytest
from unittest.mock import patch, MagicMock
from decimal import Decimal
import requests
from kiosk.services.economics import EconomicsService
from kiosk.config import Config

class TestEconomicsService:
    def test_get_headers(self):
        Config.ECO_GRANT_TOKEN = 'test_grant_token'
        Config.ECO_SECRET_TOKEN = 'test_secret_token'
        
        headers = EconomicsService._get_headers()
        assert headers['X-AgreementGrantToken'] == 'test_grant_token'
        assert headers['X-AppSecretToken'] == 'test_secret_token'
        assert headers['Content-Type'] == 'application/json'
        assert 'Idempotency-Key' not in headers
        
        headers_with_idem = EconomicsService._get_headers('my_idem_key')
        assert headers_with_idem['Idempotency-Key'] == 'my_idem_key'

    @patch('kiosk.services.economics.requests.get')
    def test_request_get_success(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = {"status": "ok"}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        result = EconomicsService._request('GET', 'http://test.url')
        assert result == {"status": "ok"}
        mock_get.assert_called_once()
        
    @patch('kiosk.services.economics.requests.post')
    def test_request_post_success(self, mock_post):
        mock_response = MagicMock()
        mock_response.json.return_value = {"id": 123}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response
        
        result = EconomicsService._request('POST', 'http://test.url', data={"foo": "bar"}, key="test-key")
        assert result == {"id": 123}
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        assert kwargs['json'] == {"foo": "bar"}
        assert 'Idempotency-Key' in kwargs['headers']
        assert kwargs['headers']['Idempotency-Key'] == 'test-key'

    @patch('kiosk.services.economics.requests.get')
    def test_request_http_error(self, mock_get):
        mock_response = MagicMock()
        mock_response.text = "Error detail"
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(response=mock_response)
        mock_get.return_value = mock_response
        
        with pytest.raises(requests.exceptions.HTTPError):
            EconomicsService._request('GET', 'http://test.url')

    @patch('kiosk.services.economics.EconomicsService._request')
    @patch('kiosk.services.economics.get_db_connection')
    def test_update_users_success(self, mock_db, mock_request):
        # Mock API Response
        mock_request.return_value = {
            'collection': [
                {'customerNumber': 1, 'name': 'User One', 'customerGroup': {'customerGroupNumber': 10}},
                {'customerNumber': 2, 'name': 'User Two', 'customerGroup': {'customerGroupNumber': 20}}
            ]
        }
        
        # Mock DB
        mock_conn = MagicMock()
        mock_curs = MagicMock()
        mock_db.return_value.__enter__.return_value = mock_conn
        mock_conn.transaction.return_value.__enter__.return_value = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_curs
        
        # Existing DB users
        mock_curs.fetchall.return_value = [
            {'customerid': 1}, # Exists in API
            {'customerid': 3}  # Not in API, should be deleted
        ]
        
        EconomicsService.update_users()
        
        # Verify API called
        mock_request.assert_called_once()
        
        # Verify executemany called twice (one for delete, one for upsert)
        assert mock_curs.executemany.call_count == 2
        
        # Check first call (deletes)
        delete_call_args = mock_curs.executemany.call_args_list[0][0]
        assert "deleted = true" in delete_call_args[0]
        assert delete_call_args[1] == [(3,)]
        
        # Check second call (upserts)
        upsert_call_args = mock_curs.executemany.call_args_list[1][0]
        assert "INSERT INTO customers" in upsert_call_args[0]
        assert len(upsert_call_args[1]) == 2

    @patch('kiosk.services.economics.EconomicsService._request')
    @patch('kiosk.services.economics.get_db_connection')
    def test_update_users_pagination(self, mock_db, mock_request):
        # Mock API Response with pagination
        mock_request.side_effect = [
            {
                'collection': [
                    {'customerNumber': 1, 'name': 'User One', 'customerGroup': {'customerGroupNumber': 10}},
                    {'customerNumber': 2, 'name': 'User Two', 'customerGroup': {'customerGroupNumber': 20}}
                ],
                'pagination': {'nextPage': 'https://restapi.e-conomic.com/customers?pagesize=1000&skipPages=1'}
            },
            {
                'collection': [
                    {'customerNumber': 3, 'name': 'User Three', 'customerGroup': {'customerGroupNumber': 30}}
                ]
            }
        ]
        
        # Mock DB
        mock_conn = MagicMock()
        mock_curs = MagicMock()
        mock_db.return_value.__enter__.return_value = mock_conn
        mock_conn.transaction.return_value.__enter__.return_value = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_curs
        
        mock_curs.fetchall.return_value = []
        
        EconomicsService.update_users()
        
        # Verify API called twice
        assert mock_request.call_count == 2
        
        # Verify upsert includes users from both pages (total 3)
        assert mock_curs.executemany.call_count == 1
        upsert_call_args = mock_curs.executemany.call_args_list[0][0]
        assert "INSERT INTO customers" in upsert_call_args[0]
        assert len(upsert_call_args[1]) == 3
        
    @patch('kiosk.services.economics.EconomicsService._request')
    def test_find_kiosk_draft_line_found(self, mock_request):
        # First call: get drafts for customer
        # Second call: get draft details
        mock_request.side_effect = [
            {'collection': [{'self': 'http://draft/1'}]},
            {
                'orderNumber': 1001,
                'lines': [
                    {'product': {'productNumber': 99}, 'description': 'Cola', 'unitNetPrice': 10.0, 'lineNumber': 1},
                    {'product': {'productNumber': 42}, 'description': 'Kaffe', 'unitNetPrice': 5.0, 'lineNumber': 2}
                ]
            }
        ]
        
        draft_id, line_id = EconomicsService.find_kiosk_draft_line(customerid=1, product_id=42, sold_product_name='Kaffe', sold_item_price=5.0)
        
        assert draft_id == 1001
        assert line_id == 2

    @patch('kiosk.services.economics.EconomicsService._request')
    def test_find_kiosk_draft_line_not_found_but_draft_exists(self, mock_request):
        # Draft exists but product line not found
        mock_request.side_effect = [
            {'collection': [{'self': 'http://draft/1'}]},
            {'orderNumber': 1002, 'lines': []} # empty draft
        ]
        
        draft_id, line_id = EconomicsService.find_kiosk_draft_line(customerid=1, product_id=42, sold_product_name='Kaffe', sold_item_price=5.0)
        
        assert draft_id == 1002
        assert line_id is None
        
    @patch('kiosk.services.economics.EconomicsService._request')
    def test_create_empty_order(self, mock_request):
        mock_request.side_effect = [
            {"template_data": "here"},
            {"orderNumber": 2001}
        ]
        
        draft_id = EconomicsService.create_empty_order(customerid=1, salesid=55)
        
        assert draft_id == 2001
        assert mock_request.call_args_list[0][0][0] == 'GET'
        assert mock_request.call_args_list[1][0][0] == 'POST'
        assert mock_request.call_args_list[1][1]['key'] == 'create-inv-55'
        assert mock_request.call_args_list[1][1]['data'] == {"template_data": "here"}

    @patch('kiosk.services.economics.EconomicsService._request')
    def test_update_sale_success(self, mock_request):
        mock_request.side_effect = [
            {
                'orderNumber': 3001,
                'lines': [
                    {'lineNumber': 1, 'quantity': 2, 'totalNetAmount': 20.0},
                    {'lineNumber': 2, 'quantity': 1, 'totalNetAmount': 10.0}
                ]
            },
            None # PUT request returns None typically
        ]
        
        pre_update_sum = EconomicsService.update_sale(order_draft=3001, order_line=2, value_added=3, salesid=55)
        
        assert pre_update_sum == 10.0
        assert mock_request.call_count == 2
        put_call = mock_request.call_args_list[1]
        assert put_call[0][0] == 'PUT'
        assert put_call[1]['key'] == 'upd-qty-55'
        assert put_call[1]['data']['lines'][1]['quantity'] == 4 # 1 + 3

    @patch('kiosk.services.economics.get_db_connection')
    @patch('kiosk.services.economics.EconomicsService.find_kiosk_draft_line')
    @patch('kiosk.services.economics.EconomicsService.create_draft_order_line')
    def test_sync_pending_transfers_inserts_line(self, mock_create_line, mock_find_draft, mock_db):
        mock_find_draft.return_value = (4000, None) # Draft exists, line does not
        
        mock_lock_conn = MagicMock()
        mock_lock_curs = MagicMock()
        mock_lock_curs.fetchone.return_value = [True] # Lock acquired
        
        mock_conn = MagicMock()
        mock_curs = MagicMock()
        
        # sales to process
        mock_curs.fetchall.return_value = [
            {'salesid': 100, 'customerid': 1, 'soldproductname': 'Cola', 'solditemprice': '15.00', 'quantity': 1}
        ]
        
        # Setup the multiple with statements for connections
        mock_db.side_effect = [
            MagicMock(__enter__=MagicMock(return_value=mock_lock_conn)), # lock connection
            MagicMock(__enter__=MagicMock(return_value=mock_conn)),      # main fetch connection
            MagicMock(__enter__=MagicMock(return_value=mock_conn)),      # main update connection
            MagicMock(__enter__=MagicMock(return_value=mock_conn)),      # just in case
        ]
        
        mock_lock_conn.cursor.return_value.__enter__.return_value = mock_lock_curs
        mock_conn.cursor.return_value.__enter__.return_value = mock_curs
        
        EconomicsService.sync_pending_transfers()
        
        # Verify line creation was called
        mock_create_line.assert_called_once()
        
        # Verify DB update on success
        assert mock_curs.execute.call_count >= 1
        update_call = [c for c in mock_curs.execute.call_args_list if "UPDATE ecotransfer" in c[0][0]]
        assert len(update_call) == 1
        assert "transferred=true" in update_call[0][0][0]

    @patch('kiosk.services.economics.EconomicsService._request')
    def test_update_sale_line_not_found(self, mock_request):
        """Test update_sale raises Exception when line isn't present."""
        mock_request.return_value = {
            'orderNumber': 3001,
            'lines': [
                {'lineNumber': 99, 'quantity': 1, 'totalNetAmount': 10.0} # Not the line we want
            ]
        }
        
        with pytest.raises(Exception, match="Order line 2 not found"):
            EconomicsService.update_sale(order_draft=3001, order_line=2, value_added=1, salesid=55)

    @patch('kiosk.services.economics.EconomicsService._request')
    def test_create_draft_order_line_db_flow(self, mock_request):
        """Test create_draft_order_line executes properly and creates missing lines array."""
        mock_request.side_effect = [
            {'product': {}}, # order_line GET
            {'orderNumber': 100}, # temp_draft GET without 'lines'
            None # PUT
        ]
        
        EconomicsService.create_draft_order_line(
            customerid=1, order_draft=100, product_id=5, 
            sold_product_name="Test", sold_item_price=10.0, 
            quantity=1, salesid=55
        )
        
        # Verify lines array was created and populated
        assert mock_request.call_count == 3
        put_call_data = mock_request.call_args_list[2][1]['data']
        assert 'lines' in put_call_data
        assert len(put_call_data['lines']) == 1
        assert put_call_data['lines'][0]['description'] == "Test"

    @patch('kiosk.services.economics.Config')
    @patch('kiosk.services.economics.get_db_connection')
    @patch('kiosk.services.economics.EconomicsService.find_kiosk_draft_line')
    def test_sync_pending_transfers_network_timeout(self, mock_find, mock_db, mock_config):
        """Test sync_pending_transfers handles a request timeout by skipping and not incrementing attempts."""
        mock_config.ECO_MAX_ATTEMPTS = 5
        
        # Throw connection error
        mock_find.side_effect = requests.exceptions.Timeout("API hung")
        
        mock_lock_conn = MagicMock()
        mock_lock_curs = MagicMock()
        mock_lock_curs.fetchone.return_value = [True]
        
        mock_conn = MagicMock()
        mock_curs = MagicMock()
        mock_curs.fetchall.return_value = [
            {'salesid': 101, 'customerid': 1, 'soldproductname': 'Cola', 'solditemprice': '15.00', 'quantity': 1}
        ]
        
        mock_db.side_effect = [
            MagicMock(__enter__=MagicMock(return_value=mock_lock_conn)),
            MagicMock(__enter__=MagicMock(return_value=mock_conn)),
            MagicMock(__enter__=MagicMock(return_value=mock_conn)),
        ]
        
        mock_lock_conn.cursor.return_value.__enter__.return_value = mock_lock_curs
        mock_conn.cursor.return_value.__enter__.return_value = mock_curs
        
        EconomicsService.sync_pending_transfers()
        
        # Verify error handling logged failure and marked attempts=attempts+0
        update_call = [c for c in mock_curs.execute.call_args_list if "UPDATE ecotransfer" in c[0][0]][0]
        query = update_call[0][0]
        args = update_call[0][1]
        
        assert "attempts=attempts + %s" in query
        assert args[0] == 0 # increment_attempts = false
        assert "Network/Timeout" in args[1] # errormsg

    @patch('kiosk.services.economics.Config')
    @patch('kiosk.services.economics.get_db_connection')
    @patch('kiosk.services.economics.EconomicsService.find_kiosk_draft_line')
    def test_sync_pending_transfers_http_error(self, mock_find, mock_db, mock_config):
        """Test sync_pending_transfers handles HTTP 400s (API Reject) by incrementing attempts."""
        mock_config.ECO_MAX_ATTEMPTS = 5
        
        # Throw HTTP error
        mock_find.side_effect = requests.exceptions.HTTPError("400 Bad Request")
        
        mock_lock_conn = MagicMock()
        mock_lock_curs = MagicMock()
        mock_lock_curs.fetchone.return_value = [True]
        
        mock_conn = MagicMock()
        mock_curs = MagicMock()
        mock_curs.fetchall.return_value = [
            {'salesid': 102, 'customerid': 1, 'soldproductname': 'Cola', 'solditemprice': '15.00', 'quantity': 1}
        ]
        
        mock_db.side_effect = [
            MagicMock(__enter__=MagicMock(return_value=mock_lock_conn)),
            MagicMock(__enter__=MagicMock(return_value=mock_conn)),
            MagicMock(__enter__=MagicMock(return_value=mock_conn)),
        ]
        
        mock_lock_conn.cursor.return_value.__enter__.return_value = mock_lock_curs
        mock_conn.cursor.return_value.__enter__.return_value = mock_curs
        
        EconomicsService.sync_pending_transfers()
        
        # Verify error handling logged failure and marked attempts=attempts+1
        update_call = [c for c in mock_curs.execute.call_args_list if "UPDATE ecotransfer" in c[0][0]][0]
        args = update_call[0][1]
        
        assert args[0] == 1 # increment_attempts = true
        assert "API Rejected Sale" in args[1] # errormsg

    @patch('kiosk.services.economics.Config')
    @patch('kiosk.services.economics.get_db_connection')
    @patch('kiosk.services.economics.EconomicsService.find_kiosk_draft_line')
    def test_sync_pending_transfers_general_error(self, mock_find, mock_db, mock_config):
        """Test sync_pending_transfers handles generic Python exceptions."""
        mock_config.ECO_MAX_ATTEMPTS = 5
        
        # Throw standard Exception
        mock_find.side_effect = Exception("System blew up randomly")
        
        mock_lock_conn = MagicMock()
        mock_lock_curs = MagicMock()
        mock_lock_curs.fetchone.return_value = [True]
        
        mock_conn = MagicMock()
        mock_curs = MagicMock()
        mock_curs.fetchall.return_value = [
            {'salesid': 103, 'customerid': 1, 'soldproductname': 'Cola', 'solditemprice': '15.00', 'quantity': 1}
        ]
        
        mock_db.side_effect = [
            MagicMock(__enter__=MagicMock(return_value=mock_lock_conn)),
            MagicMock(__enter__=MagicMock(return_value=mock_conn)),
            MagicMock(__enter__=MagicMock(return_value=mock_conn)),
        ]
        
        mock_lock_conn.cursor.return_value.__enter__.return_value = mock_lock_curs
        mock_conn.cursor.return_value.__enter__.return_value = mock_curs
        
        EconomicsService.sync_pending_transfers()
        
        # Verify error handling logged failure and marked attempts=attempts+1
        update_call = [c for c in mock_curs.execute.call_args_list if "UPDATE ecotransfer" in c[0][0]][0]
        args = update_call[0][1]
        
        assert args[0] == 1 # increment_attempts = true
        assert "General Error" in args[1] # errormsg

    @patch('kiosk.services.economics.get_db_connection')
    def test_sync_pending_transfers_lock_acquisition_failure(self, mock_db):
        """Test sync_pending_transfers aborts smoothly when it errors getting the pg_advisory_lock."""
        mock_db.side_effect = Exception('Database unreachable entirely')
        
        # Should catch and not crash
        EconomicsService.sync_pending_transfers()
