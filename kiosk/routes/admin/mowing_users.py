from flask import render_template, request, redirect, url_for, flash, current_app
import psycopg
from ...database import get_db_connection
from . import bp, admin_required

@bp.route('/greenteam')
@admin_required
def mowing_user_list():
    try:
        with get_db_connection() as conn:
            with conn.cursor(row_factory=psycopg.rows.dict_row) as curs:
                # Get current mowing users
                curs.execute("""
                    SELECT c.customerid, c.customername 
                    FROM mowingusers m
                    JOIN customers c ON m.customerid = c.customerid
                    ORDER BY c.customername
                """)
                mowing_users = curs.fetchall()
                
                # Get available customers that are NOT in the mowing team yet
                curs.execute("""
                    SELECT customerid, customername 
                    FROM customers 
                    WHERE deleted = false 
                    AND customerid NOT IN (SELECT customerid FROM mowingusers)
                    ORDER BY customername
                """)
                available_customers = curs.fetchall()
                
        return render_template('admin/mowing_users.html', mowing_users=mowing_users, available_customers=available_customers)
    except Exception as e:
        current_app.logger.error(f"Error loading greenteam members: {e}")
        flash("Der opstod en fejl ved hentning af Greenteam medlemmer.", "error")
        return redirect(url_for('admin.product_list'))

@bp.route('/greenteam/add', methods=['POST'])
@admin_required
def mowing_user_add():
    customer_id = request.form.get('customerid')
    if not customer_id:
        flash("Du skal vælge et medlem fra listen.", "error")
        return redirect(url_for('admin.mowing_user_list'))
        
    try:
        with get_db_connection() as conn:
            with conn.transaction():
                with conn.cursor() as curs:
                    curs.execute("INSERT INTO mowingusers (customerid) VALUES (%s)", (customer_id,))
        flash("Medlem tilføjet til Greenteamet.", "success")
    except psycopg.errors.UniqueViolation:
         flash("Medlemmet er allerede en del af Greenteamet.", "error")
    except Exception as e:
        current_app.logger.error(f"Error adding greenteam member {customer_id}: {e}")
        flash("Der opstod en systemfejl ved tilføjelse af medlemmet.", "error")
        
    return redirect(url_for('admin.mowing_user_list'))

@bp.route('/greenteam/<int:id>/delete', methods=['POST'])
@admin_required
def mowing_user_delete(id):
    try:
        with get_db_connection() as conn:
            with conn.transaction():
                with conn.cursor() as curs:
                    curs.execute("DELETE FROM mowingusers WHERE customerid = %s", (id,))
        flash("Medlemmet er fjernet fra Greenteamet.", "success")
    except Exception as e:
        current_app.logger.error(f"Error deleting greenteam member {id}: {e}")
        flash("Der opstod en fejl ved fjernelse af medlemmet.", "error")
        
    return redirect(url_for('admin.mowing_user_list'))
