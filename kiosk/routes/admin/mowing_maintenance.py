from flask import render_template, request, redirect, url_for, flash, current_app
import psycopg
from ...database import get_db_connection
from . import bp, admin_required

@bp.route('/maintenance')
@admin_required
def maintenance_list():
    try:
        with get_db_connection() as conn:
            with conn.cursor(row_factory=psycopg.rows.dict_row) as curs:
                curs.execute("SELECT * FROM mowingmaintenance ORDER BY interval_h")
                maintenance_items = curs.fetchall()
        return render_template('admin/maintenance_list.html', maintenance_items=maintenance_items)
    except Exception as e:
        current_app.logger.error(f"Error listing maintenance items: {e}")
        flash("Der opstod en fejl ved hentning af vedligeholdelsesopgaver.", "error")
        return redirect(url_for('admin.mowing_user_list'))

@bp.route('/maintenance/new', methods=['GET', 'POST'])
@admin_required
def maintenance_new():
    if request.method == 'POST':
        return _handle_maintenance_save()
    return render_template('admin/maintenance_form.html', maintenance=None)

@bp.route('/maintenance/<int:id>/edit', methods=['GET', 'POST'])
@admin_required
def maintenance_edit(id):
    if request.method == 'POST':
        return _handle_maintenance_save(id)

    try:
        with get_db_connection() as conn:
            with conn.cursor(row_factory=psycopg.rows.dict_row) as curs:
                curs.execute("SELECT * FROM mowingmaintenance WHERE id = %s", (id,))
                maintenance = curs.fetchone()
        
        if not maintenance:
            flash("Opgaven blev ikke fundet.", "error")
            return redirect(url_for('admin.maintenance_list'))
            
        return render_template('admin/maintenance_form.html', maintenance=maintenance)

    except Exception as e:
        current_app.logger.error(f"Error fetching maintenance item {id}: {e}")
        flash("Der opstod en fejl ved hentning af opgaven.", "error")
        return redirect(url_for('admin.maintenance_list'))

@bp.route('/maintenance/<int:id>/delete', methods=['POST'])
@admin_required
def maintenance_delete(id):
    try:
        with get_db_connection() as conn:
            with conn.transaction():
                with conn.cursor() as curs:
                    curs.execute("DELETE FROM mowingmaintenance WHERE id = %s", (id,))
            flash("Vedligeholdelsesopgave slettet.", "success")
    except Exception as e:
        current_app.logger.error(f"Error deleting maintenance item {id}: {e}")
        flash("Der opstod en fejl ved sletning af opgaven.", "error")
        
    return redirect(url_for('admin.maintenance_list'))

def _handle_maintenance_save(maintenance_id=None):
    maintenance_type = request.form.get('maintenance_type')
    interval_h = request.form.get('interval_h')

    try:
        interval_h = float(interval_h)
        with get_db_connection() as conn:
            with conn.transaction():
                with conn.cursor() as curs:
                    if maintenance_id:
                        curs.execute("""
                            UPDATE mowingmaintenance 
                            SET maintenance_type=%s, interval_h=%s
                            WHERE id=%s
                        """, (maintenance_type, interval_h, maintenance_id))
                    else:
                        curs.execute("""
                            INSERT INTO mowingmaintenance (maintenance_type, interval_h)
                            VALUES (%s, %s)
                        """, (maintenance_type, interval_h))
            
        flash("Opgave gemt.", "success")
        return redirect(url_for('admin.maintenance_list'))

    except ValueError:
        flash("Intervallet skal være et tal (f.eks. 15).", "error")
        return render_template('admin/maintenance_form.html', maintenance=request.form)
    except Exception as e:
        current_app.logger.error(f"Error saving maintenance item: {e}")
        flash("Der opstod en systemfejl ved gemning af opgaven.", "error")
        return render_template('admin/maintenance_form.html', maintenance=request.form if not maintenance_id else None)
