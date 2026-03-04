from flask import Blueprint, render_template, request, redirect, url_for, session, current_app, flash
from ..database import get_db_connection
import psycopg
from psycopg import errors
import os
import time
import threading
from werkzeug.utils import secure_filename

bp = Blueprint('admin', __name__, url_prefix='/admin')

# PIN brute-force protection: track failed attempts per IP
_pin_attempts = {}  # {ip: (fail_count, last_fail_timestamp)}
_pin_lock = threading.Lock()

def _validate_image(file_storage):
    """Validate an uploaded image file. Returns (ok, error_message)."""
    allowed = current_app.config['ALLOWED_IMAGE_EXTENSIONS']
    max_size = current_app.config['MAX_IMAGE_SIZE_BYTES']

    filename = file_storage.filename or ''
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
    if ext not in allowed:
        allowed_str = ', '.join(sorted(allowed))
        return False, f"Filtypen '.{ext}' er ikke tilladt. Tilladte: {allowed_str}"
    
    file_storage.seek(0, 2)  # seek to end
    size = file_storage.tell()
    file_storage.seek(0)     # reset to start
    if size > max_size:
        max_kb = max_size // 1024
        return False, f"Filen er for stor ({size // 1024} KB). Maks: {max_kb} KB."
    
    return True, None

def admin_required(f):
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        customer_id = session.get('customerid')
        
        # 1. Must be logged in as a valid customer
        if not customer_id:
            return redirect(url_for('auth.login'))
            
        # 2. Must be in the allowed admin list
        if customer_id not in current_app.config['ADMIN_USER_IDS']:
             flash("Du har ikke adgang til admin-panelet.")
             return redirect(url_for('main.index'))

        # 3. Must have entered the PIN
        if not session.get('admin_authenticated'):
            return redirect(url_for('admin.login'))
            
        return f(*args, **kwargs)
    return decorated_function

@bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        ip = request.remote_addr or 'unknown'
        max_attempts = current_app.config['ADMIN_PIN_MAX_ATTEMPTS']
        lockout_seconds = current_app.config['ADMIN_PIN_LOCKOUT_SECONDS']

        with _pin_lock:
            fail_count, last_fail = _pin_attempts.get(ip, (0, 0))
            # Reset counter if lockout period has passed
            if fail_count >= max_attempts and (time.monotonic() - last_fail) >= lockout_seconds:
                fail_count = 0
            if fail_count >= max_attempts:
                remaining = int(lockout_seconds - (time.monotonic() - last_fail))
                return render_template('admin/login.html', error=f"For mange forsøg. Prøv igen om {remaining} sekunder.")

        pin = request.form.get('pin')
        if pin == current_app.config['ADMIN_PIN']:
            with _pin_lock:
                _pin_attempts.pop(ip, None)
            session['admin_authenticated'] = True
            return redirect(url_for('admin.product_list'))
        else:
            with _pin_lock:
                _pin_attempts[ip] = (fail_count + 1, time.monotonic())
            return render_template('admin/login.html', error="Forkert PIN kode")
    
    return render_template('admin/login.html')

@bp.route('/products')
@admin_required
def product_list():
    try:
        with get_db_connection() as conn:
            with conn.cursor(row_factory=psycopg.rows.dict_row) as curs:
                curs.execute("SELECT * FROM products ORDER BY sorting, productname")
                products = curs.fetchall()
        return render_template('admin/product_list.html', products=products)
    except Exception as e:
        current_app.logger.error(f"Error listing products: {e}")
        flash("Kunne ikke hente produkter.")
        return redirect(url_for('main.index'))

@bp.route('/images')
@admin_required
def image_gallery():
    image_dir = os.path.join(current_app.root_path, 'static', 'images')
    try:
        images = [f for f in os.listdir(image_dir) if os.path.isfile(os.path.join(image_dir, f))]
        images.sort()
    except Exception as e:
        current_app.logger.error(f"Error reading image directory: {e}")
        images = []
        flash("Kunne ikke læse billedmappen.")
    
    return render_template('admin/image_gallery.html', images=images)

@bp.route('/images/upload', methods=['POST'])
@admin_required
def image_upload():
    image_file = request.files.get('imagefile')
    if image_file and image_file.filename:
        ok, error = _validate_image(image_file)
        if not ok:
            flash(error)
            return redirect(url_for('admin.image_gallery'))
        filename = secure_filename(image_file.filename)
        save_path = os.path.join(current_app.root_path, 'static', 'images', filename)
        image_file.save(save_path)
        flash(f"Billede '{filename}' uploadet.")
    else:
        flash("Ingen fil valgt.")
    return redirect(url_for('admin.image_gallery'))

@bp.route('/images/delete/<filename>', methods=['POST'])
@admin_required
def image_delete(filename):
    filename = secure_filename(filename)
    image_path = os.path.join(current_app.root_path, 'static', 'images', filename)
    
    # Optional: Check if used by products
    try:
        with get_db_connection() as conn:
            with conn.cursor() as curs:
                curs.execute("SELECT COUNT(*) FROM products WHERE imagefilename = %s", (filename,))
                count = curs.fetchone()[0]
        
        if count > 0:
            flash(f"Billedet '{filename}' bruges af {count} produkt(er) og kan ikke slettes.")
        else:
            if os.path.exists(image_path):
                os.remove(image_path)
                flash(f"Billede '{filename}' slettet.")
            else:
                flash("Filen findes ikke.")
    except Exception as e:
        current_app.logger.error(f"Error deleting image: {e}")
        flash("Fejl ved sletning af billede.")
        
    return redirect(url_for('admin.image_gallery'))

@bp.route('/products/new', methods=['GET', 'POST'])
@admin_required
def product_new():
    if request.method == 'POST':
        return _handle_product_save()
    
    images = _get_available_images()
    return render_template('admin/product_form.html', product=None, images=images)

@bp.route('/products/<int:id>/edit', methods=['GET', 'POST'])
@admin_required
def product_edit(id):
    if request.method == 'POST':
        return _handle_product_save(id)

    try:
        with get_db_connection() as conn:
            with conn.cursor(row_factory=psycopg.rows.dict_row) as curs:
                curs.execute("SELECT * FROM products WHERE productid = %s", (id,))
                product = curs.fetchone()
        
        if not product:
            flash("Produkt ikke fundet.")
            return redirect(url_for('admin.product_list'))
            
        images = _get_available_images()
        return render_template('admin/product_form.html', product=product, images=images)

    except Exception as e:
        current_app.logger.error(f"Error fetching product {id}: {e}")
        flash("Fejl ved hentning af produkt.")
        return redirect(url_for('admin.product_list'))

@bp.route('/products/<int:id>/delete', methods=['POST'])
@admin_required
def product_delete(id):
    try:
        with get_db_connection() as conn:
            with conn.cursor() as curs:
                # 1. Check if product is referenced in sales
                curs.execute("SELECT COUNT(*) FROM sales WHERE productid = %s", (id,))
                count = curs.fetchone()[0]
                
                if count > 0:
                    flash(f"Produktet kan ikke slettes, da det er knyttet til {count} salg. Overvej at deaktivere det i stedet.")
                    return redirect(url_for('admin.product_list'))
                
                # 2. Proceed with deletion
                curs.execute("DELETE FROM products WHERE productid = %s", (id,))
            conn.commit()
            
        flash("Produkt slettet.")
    except Exception as e:
        current_app.logger.error(f"Error deleting product {id}: {e}")
        flash("Fejl ved sletning af produkt.")
        
    return redirect(url_for('admin.product_list'))

def _get_available_images():
    image_dir = os.path.join(current_app.root_path, 'static', 'images')
    try:
        return [f for f in os.listdir(image_dir) if os.path.isfile(os.path.join(image_dir, f))]
    except:
        return []

def _handle_product_save(product_id=None):
    productname = request.form.get('productname')
    itemprice = request.form.get('itemprice')
    sorting = request.form.get('sorting', 100)
    disabled = request.form.get('disabled') == 'on'
    
    # Check for selected image from gallery first, then fall back to upload
    selected_image = request.form.get('selected_image')
    image_file = request.files.get('imagefile')
    
    if image_file and image_file.filename:
        ok, error = _validate_image(image_file)
        if not ok:
            flash(error)
            images = _get_available_images()
            return render_template('admin/product_form.html', product=request.form, images=images)
        image_filename = secure_filename(image_file.filename)
        save_path = os.path.join(current_app.root_path, 'static', 'images', image_filename)
        image_file.save(save_path)
    elif selected_image:
        image_filename = selected_image
    else:
        # Fallback to current image if editing
        image_filename = request.form.get('current_image')

    if not image_filename and not product_id:
         flash("Billede er påkrævet for nye produkter.")
         images = _get_available_images()
         return render_template('admin/product_form.html', product=request.form, images=images)

    try:
        with get_db_connection() as conn:
            with conn.cursor() as curs:
                if product_id:
                    curs.execute("""
                        UPDATE products 
                        SET productname=%s, itemprice=%s, imagefilename=%s, disabled=%s, sorting=%s
                        WHERE productid=%s
                    """, (productname, itemprice, image_filename, disabled, sorting, product_id))
                else:
                    curs.execute("""
                        INSERT INTO products (productname, itemprice, imagefilename, disabled, sorting)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (productname, itemprice, image_filename, disabled, sorting))
            conn.commit()
            
        flash("Produkt gemt.")
        return redirect(url_for('admin.product_list'))

    except Exception as e:
        current_app.logger.error(f"Error saving product: {e}")
        flash(f"Fejl ved gemning: {e}")
        images = _get_available_images()
        return render_template('admin/product_form.html', product=None, images=images) 


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
        flash("Fejl ved hentning af Greenteam medlemmer.")
        return redirect(url_for('admin.product_list'))


@bp.route('/greenteam/add', methods=['POST'])
@admin_required
def mowing_user_add():
    customer_id = request.form.get('customerid')
    if not customer_id:
        flash("Du skal vælge et medlem.")
        return redirect(url_for('admin.mowing_user_list'))
        
    try:
        with get_db_connection() as conn:
            with conn.cursor() as curs:
                curs.execute("INSERT INTO mowingusers (customerid) VALUES (%s)", (customer_id,))
            conn.commit()
        flash("Medlem tilføjet til Greenteam.")
    except psycopg.errors.UniqueViolation:
         flash("Medlemmet er allerede i Greenteam.")
    except Exception as e:
        current_app.logger.error(f"Error adding greenteam member {customer_id}: {e}")
        flash("Fejl ved tilføjelse af medlem.")
        
    return redirect(url_for('admin.mowing_user_list'))


@bp.route('/greenteam/<int:id>/delete', methods=['POST'])
@admin_required
def mowing_user_delete(id):
    try:
        with get_db_connection() as conn:
            with conn.cursor() as curs:
                curs.execute("DELETE FROM mowingusers WHERE customerid = %s", (id,))
            conn.commit()
        flash("Medlem fjernet fra Greenteam.")
    except Exception as e:
        current_app.logger.error(f"Error deleting greenteam member {id}: {e}")
        flash("Fejl ved fjernelse af medlem.")
        
    return redirect(url_for('admin.mowing_user_list'))


# --- MOWING SECTIONS ADMIN ---

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
        flash("Kunne ikke hente klippeområder.")
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
            flash("Område ikke fundet.")
            return redirect(url_for('admin.section_list'))
            
        return render_template('admin/section_form.html', section=section)

    except Exception as e:
        current_app.logger.error(f"Error fetching section {id}: {e}")
        flash("Fejl ved hentning af område.")
        return redirect(url_for('admin.section_list'))

@bp.route('/sections/<int:id>/delete', methods=['POST'])
@admin_required
def section_delete(id):
    try:
        with get_db_connection() as conn:
            with conn.transaction():
                with conn.cursor() as curs:
                    curs.execute("DELETE FROM mowingsections WHERE id = %s", (id,))
            flash("Område slettet.")
    except Exception as e:
        # If there's history, disable it instead of deleting
        if 'mowingactivities' in str(e) or 'foreign key' in str(e).lower() or getattr(e, 'sqlstate', None) == '23503':
            try:
                with get_db_connection() as conn:
                    with conn.cursor() as curs:
                        curs.execute("UPDATE mowingsections SET disabled = true WHERE id = %s", (id,))
                    conn.commit()
                flash("Området kunne ikke slettes pga. klippehistorik. Det er i stedet blevet deaktiveret og skjult for brugerne.")
            except Exception as update_err:
                current_app.logger.error(f"Error disabling section {id}: {update_err}")
                flash("Fejl ved deaktivering af område.")
    except Exception as e:
        current_app.logger.error(f"Error deleting section {id}: {e}")
        flash("Fejl ved sletning af område.")
        
    return redirect(url_for('admin.section_list'))

def _handle_section_save(section_id=None):
    section_name = request.form.get('section_name')
    cutting_time = request.form.get('cutting_time_in_h')
    disabled = request.form.get('disabled') == 'on'

    try:
        cutting_time = float(cutting_time)
        with get_db_connection() as conn:
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
            conn.commit()
            
        flash("Område gemt.")
        return redirect(url_for('admin.section_list'))

    except ValueError:
        flash("Tidsestimat skal være et tal (f.eks. 1.5).")
        return render_template('admin/section_form.html', section=request.form)
    except Exception as e:
        current_app.logger.error(f"Error saving section: {e}")
        flash(f"Fejl ved gemning: {e}")
        return render_template('admin/section_form.html', section=request.form if not section_id else None)


# --- MOWING MAINTENANCE ADMIN ---

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
        flash("Kunne ikke hente vedligeholdelsesopgaver.")
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
            flash("Opgave ikke fundet.")
            return redirect(url_for('admin.maintenance_list'))
            
        return render_template('admin/maintenance_form.html', maintenance=maintenance)

    except Exception as e:
        current_app.logger.error(f"Error fetching maintenance item {id}: {e}")
        flash("Fejl ved hentning af opgave.")
        return redirect(url_for('admin.maintenance_list'))

@bp.route('/maintenance/<int:id>/delete', methods=['POST'])
@admin_required
def maintenance_delete(id):
    try:
        with get_db_connection() as conn:
            with conn.transaction():
                with conn.cursor() as curs:
                    curs.execute("DELETE FROM mowingmaintenance WHERE id = %s", (id,))
            flash("Vedligeholdelsesopgave slettet.")
    except Exception as e:
        current_app.logger.error(f"Error deleting maintenance item {id}: {e}")
        flash("Fejl ved sletning af opgave.")
        
    return redirect(url_for('admin.maintenance_list'))

def _handle_maintenance_save(maintenance_id=None):
    maintenance_type = request.form.get('maintenance_type')
    interval_h = request.form.get('interval_h')

    try:
        interval_h = float(interval_h)
        with get_db_connection() as conn:
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
            conn.commit()
            
        flash("Opgave gemt.")
        return redirect(url_for('admin.maintenance_list'))

    except ValueError:
        flash("Intervallet skal være et tal (f.eks. 15).")
        return render_template('admin/maintenance_form.html', maintenance=request.form)
    except Exception as e:
        current_app.logger.error(f"Error saving maintenance item: {e}")
        flash(f"Fejl ved gemning: {e}")
        return render_template('admin/maintenance_form.html', maintenance=request.form if not maintenance_id else None)
