import os
import sys
import datetime
from flask import Flask, render_template
import psycopg
from psycopg.rows import dict_row
from psycopg.conninfo import make_conninfo
from psycopg_pool import ConnectionPool
from dotenv import load_dotenv

# Load environment variables explicitly from .env.public in the root directory
env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env.public')
load_dotenv(env_path)

app = Flask(__name__)

# Fetch database credentials from environment variables
DB_HOST = os.environ.get('DB_HOST', 'postgres')
DB_PORT = os.environ.get('DB_PORT', '5432')
DB_NAME = os.environ.get('POSTGRES_DB', os.environ.get('DB_NAME', 'KioskPOS'))
DB_USER = os.environ.get('POSTGRES_USER', os.environ.get('DB_USER', 'KioskPOS'))
DB_PASSWORD = os.environ.get('DB_PASSWORD')

if not DB_PASSWORD:
    raise ValueError("No DB_PASSWORD set for Public Flask application")

conninfo = make_conninfo(
    host=DB_HOST,
    port=DB_PORT,
    dbname=DB_NAME,
    user=DB_USER,
    password=DB_PASSWORD
)
pool = ConnectionPool(conninfo, reconnect_timeout=2, timeout=5.0)

def get_db_connection():
    return pool.connection()

def get_maintenance_items(curs):
    curs.execute("SELECT * FROM maintenancestatus")
    return curs.fetchall()

@app.route('/')
def mowing_status():
    try:
        with get_db_connection() as conn:
            with conn.cursor(row_factory=dict_row) as curs:
                curs.execute("SELECT * FROM mowinghistory LIMIT 100")
                mowing_history = curs.fetchall()
                
                # 2. Last Mowed
                curs.execute("SELECT * FROM lastmowed")
                last_mowed = curs.fetchall()
                
                # 3. Overdue Maintenance
                maintenance_items = get_maintenance_items(curs)
                overdue_maintenance = [item for item in maintenance_items if item['remaining_h'] <= 0]
                
        return render_template('index.html', 
                               mowing_history=mowing_history, 
                               last_mowed=last_mowed, 
                               overdue_maintenance=overdue_maintenance)
    except Exception as e:
        print(f"Error accessing database: {e}")
        return render_template('index.html', error=str(e), mowing_history=[], last_mowed=[], overdue_maintenance=[])

@app.route('/health')
def health():
    return "OK", 200

if __name__ == '__main__':
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5000
    app.run(host='0.0.0.0', port=port, debug=True)
