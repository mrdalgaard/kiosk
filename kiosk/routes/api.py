
from flask import Blueprint, render_template, jsonify, current_app, send_from_directory
from ..database import get_db_connection
from ..config import Config
import psycopg

bp = Blueprint('api', __name__)

@bp.route('/customerlist', methods=['GET', 'POST'])
def customer_list():
    error_msg = None
    customers = []
    try:
        with get_db_connection() as conn:
            with conn.cursor(row_factory=psycopg.rows.dict_row) as curs:
                curs.execute("SELECT * FROM customers where deleted = false and customergroup = ANY(%s) ORDER by customername", (Config.CUSTOMER_GROUPS,))
                customers = curs.fetchall()

    except Exception as e:
        current_app.logger.error(f"Database unavailable on customerlist load: {e}")
        error_msg = 'Systemfejl: Kunne ikke forbinde til databasen.'

    if error_msg:
        return render_template('login.html', error=error_msg)
    else:
        return render_template('customerlist.html', customerList=customers)

@bp.route('/health')
def health_check():
    try:
        # Force a network round-trip to the DB
        with get_db_connection() as conn:
            with conn.cursor() as curs:
                curs.execute("SELECT 1")
        return jsonify({'status': 'healthy'}), 200
    except Exception as e:
        # If DB is down, pool.connection() throws an error
        return jsonify({'status': 'unhealthy', 'reason': str(e)}), 500

@bp.route('/service-worker.js')
def service_worker():
    response = send_from_directory(current_app.static_folder, 'service-worker.js', mimetype='application/javascript')
    # Prevent caching of the service worker itself
    response.headers['Cache-Control'] = 'no-cache'
    return response
