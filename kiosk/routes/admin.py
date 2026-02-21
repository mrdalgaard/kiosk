from flask import Blueprint, render_template, request, redirect, url_for, session, current_app, flash
from ..database import get_db_connection
import psycopg
import os
from werkzeug.utils import secure_filename

bp = Blueprint('admin', __name__, url_prefix='/admin')

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
        pin = request.form.get('pin')
        if pin == current_app.config['ADMIN_PIN']:
            session['admin_authenticated'] = True
            return redirect(url_for('admin.product_list'))
        else:
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
