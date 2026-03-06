from flask import render_template, request, redirect, url_for, flash, current_app
import psycopg
from ...database import get_db_connection
from . import bp, admin_required

@bp.route('/sections')
@admin_required
def section_list():
    try:
        with get_db_connection() as conn:
            with conn.cursor(row_factory=psycopg.rows.dict_row) as curs:
                curs.execute("SELECT * FROM mowingsections ORDER BY section_name")
                sections = curs.fetchall()
        return render_template('admin/sections_list.html', sections=sections)
    except Exception as e:
        current_app.logger.error(f"Error listing sections: {e}")
        flash("Der opstod en fejl ved hentning af klippeområder.", "error")
        return redirect(url_for('admin.mowing_user_list'))

@bp.route('/sections/new', methods=['GET', 'POST'])
@admin_required
def section_new():
    if request.method == 'POST':
        return _handle_section_save()
    return render_template('admin/section_form.html', section=None)

@bp.route('/sections/<int:id>/edit', methods=['GET', 'POST'])
@admin_required
def section_edit(id):
    if request.method == 'POST':
        return _handle_section_save(id)

    try:
        with get_db_connection() as conn:
            with conn.cursor(row_factory=psycopg.rows.dict_row) as curs:
                curs.execute("SELECT * FROM mowingsections WHERE id = %s", (id,))
                section = curs.fetchone()
        
        if not section:
            flash("Området blev ikke fundet.", "error")
            return redirect(url_for('admin.section_list'))
            
        return render_template('admin/section_form.html', section=section)

    except Exception as e:
        current_app.logger.error(f"Error fetching section {id}: {e}")
        flash("Der opstod en fejl ved hentning af området.", "error")
        return redirect(url_for('admin.section_list'))

@bp.route('/sections/<int:id>/delete', methods=['POST'])
@admin_required
def section_delete(id):
    try:
        with get_db_connection() as conn:
            with conn.transaction():
                with conn.cursor() as curs:
                    curs.execute("DELETE FROM mowingsections WHERE id = %s", (id,))
            flash("Området er slettet.", "success")
    except Exception as e:
        # If there's history, disable it instead of deleting
        if 'mowingactivities' in str(e) or 'foreign key' in str(e).lower() or getattr(e, 'sqlstate', None) == '23503':
            try:
                with get_db_connection() as conn:
                    with conn.transaction():
                        with conn.cursor() as curs:
                            curs.execute("UPDATE mowingsections SET disabled = true WHERE id = %s", (id,))
                flash("Området kunne ikke slettes pga. klippehistorik. Det er i stedet blevet deaktiveret og skjult for brugerne.", "error")
            except Exception as update_err:
                current_app.logger.error(f"Error disabling section {id}: {update_err}")
                flash("Der opstod en fejl ved deaktivering af området.", "error")
        else:
            current_app.logger.error(f"Error deleting section {id}: {e}")
            flash("Der opstod en fejl ved sletning af området.", "error")
        
    return redirect(url_for('admin.section_list'))

def _handle_section_save(section_id=None):
    section_name = request.form.get('section_name')
    cutting_time = request.form.get('cutting_time_in_h')
    disabled = request.form.get('disabled') == 'on'

    try:
        cutting_time = float(cutting_time)
        with get_db_connection() as conn:
            with conn.transaction():
                with conn.cursor() as curs:
                    if section_id:
                        curs.execute("""
                            UPDATE mowingsections 
                            SET section_name=%s, cutting_time_in_h=%s, disabled=%s
                            WHERE id=%s
                        """, (section_name, cutting_time, disabled, section_id))
                    else:
                        curs.execute("""
                            INSERT INTO mowingsections (section_name, cutting_time_in_h, disabled)
                            VALUES (%s, %s, %s)
                        """, (section_name, cutting_time, disabled))
            
        flash("Område gemt.", "success")
        return redirect(url_for('admin.section_list'))

    except ValueError:
        flash("Tidsestimatet skal være et tal (f.eks. 1.5).", "error")
        return render_template('admin/section_form.html', section=request.form)
    except Exception as e:
        current_app.logger.error(f"Error saving section: {e}")
        flash("Der opstod en systemfejl ved gemning af området.", "error")
        return render_template('admin/section_form.html', section=request.form if not section_id else None)
