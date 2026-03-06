import os
import sys
import datetime
import logging
from flask import Flask, render_template
import psycopg
from psycopg.rows import dict_row
from psycopg.conninfo import make_conninfo
from psycopg_pool import ConnectionPool
from dotenv import load_dotenv

# Load environment variables explicitly from .env.public in the root directory
env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env.public')
load_dotenv(env_path)

class ColorFormatter(logging.Formatter):
    """Custom logger formatter that adds color based on level."""
    
    grey = "\x1b[38;20m"
    yellow = "\x1b[33;20m"
    red = "\x1b[31;20m"
    bold_red = "\x1b[31;1m"
    reset = "\x1b[0m"
    format_str = "%(levelname)s:%(name)s:%(message)s"

    def __init__(self):
        super().__init__(fmt=self.format_str)

    def format(self, record):
        formatted = super().format(record)
        if record.levelno >= logging.ERROR:
            return self.red + formatted + self.reset
        elif record.levelno >= logging.WARNING:
            return self.yellow + formatted + self.reset
        return self.grey + formatted + self.reset

app = Flask(__name__)

# Configure Logging with Colors
log_level_str = os.environ.get('LOG_LEVEL', 'INFO').upper()
log_level = getattr(logging, log_level_str, logging.INFO)

handler = logging.StreamHandler()
handler.setFormatter(ColorFormatter())

root_logger = logging.getLogger()
root_logger.setLevel(log_level)
root_logger.handlers = [handler]

app.logger.setLevel(log_level)
for app_handler in app.logger.handlers:
    app_handler.setFormatter(ColorFormatter())

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
        app.logger.error(f"Error accessing database: {e}")
        return render_template('index.html', error=str(e), mowing_history=[], last_mowed=[], overdue_maintenance=[])

@app.route('/health')
def health():
    return "OK", 200

if __name__ == '__main__':
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5000
    app.run(host='0.0.0.0', port=port, debug=True)
