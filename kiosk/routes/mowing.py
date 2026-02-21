
from flask import Blueprint, render_template, request, redirect, url_for, session
from ..database import get_db_connection
from . import login_required
import psycopg
import datetime

bp = Blueprint('mowing', __name__)

@bp.route('/register_mowing', methods=['GET', 'POST'])
@login_required
def register_mowing():
    if request.method == 'POST':
        user_id = session.get('customerid')
        date = request.form.get('date')
        if user_id and date:
            if date > str(datetime.date.today()):
                date = str(datetime.date.today())
                
            if date == str(datetime.date.today()):
                timestamp_val = datetime.datetime.now().astimezone()
            else:
                timestamp_val = date
            with get_db_connection() as conn:
                with conn.transaction(): 
                    with conn.cursor() as curs:
                        for key, value in request.form.items():
                            if key.startswith('status_') and value != 'NotMowed':
                                section_id = key.split('_')[1]
                                curs.execute(
                                    "INSERT INTO mowingactivities (user_id, timestamp, section_id, status) VALUES (%s, %s, %s, %s)",
                                    (user_id, timestamp_val, int(section_id), value)
                                )
            return redirect(url_for('mowing.mowing_status'))
    
    today_date = str(datetime.date.today())
    
    with get_db_connection() as conn:
        with conn.cursor(row_factory=psycopg.rows.dict_row) as curs:
            curs.execute("SELECT * FROM mowingsections ORDER by id")
            sections = curs.fetchall()
    
    return render_template('register_mowing.html', sections=sections, today_date=today_date)


@bp.route('/mowing_status')
@login_required
def mowing_status():
    user_id = session['customerid']
    with get_db_connection() as conn:
        with conn.cursor(row_factory=psycopg.rows.dict_row) as curs:
            curs.execute("""
                SELECT TO_CHAR(m.timestamp::date, 'dd/mm/yyyy') as date, c.customername, s.section_name, m.status
                FROM mowingactivities m
                JOIN mowingsections s ON m.section_id = s.id
                JOIN customers c ON m.user_id = c.customerid
                ORDER BY m.id DESC
            """,)
            mowing_history = curs.fetchall()
            
            curs.execute("""
                SELECT * from (
                SELECT DISTINCT ON(s.section_name) date_part('days', now() - timestamp)::int as days, c.customername, s.section_name
                FROM mowingactivities m
                JOIN mowingsections s ON m.section_id = s.id
                JOIN customers c ON m.user_id = c.customerid
                WHERE status = '8/8'
                ORDER BY s.section_name, timestamp desc) as test
                ORDER BY days DESC
            """,)
            last_mowed = curs.fetchall()

    return render_template('mowing_status.html', mowing_history=mowing_history, last_mowed=last_mowed)

@bp.route('/mowing_maintenance')
@login_required
def mowing_maintenance():
    with get_db_connection() as conn:
        with conn.cursor(row_factory=psycopg.rows.dict_row) as curs:
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
            maintenance_items = curs.fetchall()
            
            # Calculate remaining hours dynamically without bottom cap
            for item in maintenance_items:
                item['remaining_h'] = item['interval_h'] - item['used_h']

    return render_template('mowing_maintenance.html', maintenance_items=maintenance_items)

@bp.route('/reset_maintenance/<int:maintenance_id>', methods=['POST'])
@login_required
def reset_maintenance(maintenance_id):
    user_id = session.get('customerid')
    with get_db_connection() as conn:
        with conn.transaction():
            with conn.cursor() as curs:
                curs.execute(
                    "UPDATE mowingmaintenance SET last_maintained_timestamp = CURRENT_TIMESTAMP, user_id = %s WHERE id = %s",
                    (user_id, maintenance_id)
                )
    return redirect(url_for('mowing.mowing_maintenance'))
