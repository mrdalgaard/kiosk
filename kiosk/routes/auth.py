
from flask import Blueprint, render_template, request, redirect, url_for, session, current_app
from ..database import get_db_connection
from ..services.economics import EconomicsService
from ..config import Config
import time
import psycopg

bp = Blueprint('auth', __name__)

last_customer_refresh = 0

@bp.route('/', methods=['GET', 'POST'])
def login():
    global last_customer_refresh
    error_msg = None
    result = None
    purchase_history = [] 

    # 1. Try to load initial data (and check connection)
    try:
        with get_db_connection() as conn:
            with conn.cursor(row_factory=psycopg.rows.dict_row) as curs:
                curs.execute("SELECT * FROM todayssalesgrouped")
                purchase_history = curs.fetchall()
    except Exception as e:
        current_app.logger.error(f"Database unavailable on login load: {e}")
        error_msg = 'Systemfejl: Kunne ikke forbinde til databasen.'

    # 2. Process Login (Only if DB is up)
    if request.method == 'POST' and not error_msg:
        customer_id = request.form.get('customer_id')
        if customer_id:
            try:
                with get_db_connection() as conn:
                    with conn.cursor(row_factory=psycopg.rows.dict_row) as curs:
                        curs.execute("SELECT * FROM customers WHERE customerid = %s and deleted = false", (customer_id,))
                        result = curs.fetchone()
            except Exception as e:
                current_app.logger.error(f"Database unavailable during search: {e}")
                error_msg = 'Systemfejl: Kunne ikke forbinde til databasen.'

            # Only run API logic if DB was okay, user wasn't found, and economics is enabled
            if result is None and error_msg is None and Config.ENABLE_ECONOMICS and last_customer_refresh + Config.ECO_MIN_CUSTOMER_REFRESH_INTERVAL_SEC < time.monotonic():
                last_customer_refresh = time.monotonic()
                try:
                    EconomicsService.update_users()
                    with get_db_connection() as conn:
                        with conn.cursor(row_factory=psycopg.rows.dict_row) as curs:
                            curs.execute("SELECT * FROM customers WHERE customerid = %s and deleted = false", (customer_id,))
                            result = curs.fetchone()
                except Exception as e:
                     current_app.logger.error(f"API Update failed: {e}")
            
            if result:
                session.clear()
                session['customerid'] = result['customerid']
                session['customername'] = result['customername']
                return redirect(url_for('main.index'))
            elif error_msg is None:
                error_msg = 'Medlemsnummer ikke fundet - Er du oprettet endnu af kassereren?'
        else:
            error_msg = 'Indtast medlemsnummer'

    if error_msg:
        return render_template('login.html', error=error_msg, purchasehistory=purchase_history)
    else:
        return render_template('login.html', purchasehistory=purchase_history)

@bp.route('/logout', methods=['POST', 'GET'])
def logout():
    session.clear()
    return redirect(url_for('auth.login'))
