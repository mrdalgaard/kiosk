import os
import sys
import datetime
from flask import Flask, render_template
import psycopg
from psycopg.rows import dict_row
from dotenv import load_dotenv

# Load environment variables explicitly from .env.public
env_path = os.path.join(os.path.dirname(__file__), '.env.public')
load_dotenv(env_path)

app = Flask(__name__)

# Fetch database credentials from environment variables (identical to main app)
DB_HOST = os.environ.get('DB_HOST', 'postgres')
DB_PORT = os.environ.get('DB_PORT', '5432')
DB_NAME = os.environ.get('POSTGRES_DB', os.environ.get('DB_NAME', 'KioskPOS'))
DB_USER = os.environ.get('POSTGRES_USER', os.environ.get('DB_USER', 'KioskPOS'))
DB_PASSWORD = os.environ.get('DB_PASSWORD')

if not DB_PASSWORD:
    raise ValueError("No DB_PASSWORD set for Public Flask application")

def get_db_connection():
    return psycopg.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )

def get_maintenance_items(curs):
    curs.execute("""
        SELECT 
            m.id, 
            m.maintenance_type, 
            m.interval_h, 
            m.last_maintained_timestamp,
            c.customername as maintained_by,
            COALESCE(SUM(
                s.cutting_time_in_h * 
                CAST(SPLIT_PART(a.status, '/', 1) AS FLOAT) / 
                CAST(COALESCE(NULLIF(SPLIT_PART(a.status, '/', 2), ''), '8') AS FLOAT)
            ), 0) as used_h
        FROM mowingmaintenance m
        LEFT JOIN mowingactivities a ON a.timestamp > m.last_maintained_timestamp
        LEFT JOIN mowingsections s ON a.section_id = s.id AND a.status != 'NotMowed'
        LEFT JOIN customers c ON m.user_id = c.customerid
        GROUP BY m.id, m.maintenance_type, m.interval_h, m.last_maintained_timestamp, c.customername
        ORDER BY m.id
    """)
    items = curs.fetchall()
    for item in items:
        item['remaining_h'] = item['interval_h'] - item['used_h']
    return items

@app.route('/')
def mowing_status():
    try:
        with get_db_connection() as conn:
            with conn.cursor(row_factory=dict_row) as curs:
                # 1. Mowing History (similar to main app but independent)
                curs.execute("""
                    SELECT TO_CHAR(m.timestamp::date, 'dd/mm/yyyy') as date, c.customername, s.section_name, m.status
                    FROM mowingactivities m
                    JOIN mowingsections s ON m.section_id = s.id
                    JOIN customers c ON m.user_id = c.customerid
                    ORDER BY m.id DESC
                    LIMIT 100
                """)
                mowing_history = curs.fetchall()
                
                # 2. Last Mowed
                curs.execute("""
                    SELECT * from (
                    SELECT DISTINCT ON(s.section_name) date_part('days', now() - timestamp)::int as days, c.customername, s.section_name
                    FROM mowingactivities m
                    JOIN mowingsections s ON m.section_id = s.id
                    JOIN customers c ON m.user_id = c.customerid
                    WHERE status = '8/8'
                    ORDER BY s.section_name, timestamp desc) as test
                    ORDER BY days DESC
                """)
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
