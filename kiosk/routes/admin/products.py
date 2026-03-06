from flask import render_template, request, redirect, url_for, flash, current_app
from werkzeug.utils import secure_filename
import os
import psycopg
from ...database import get_db_connection
from . import bp, admin_required
from .utils import _validate_image



def _get_available_images():
    image_dir = os.path.join(current_app.root_path, 'static', 'images')
    try:
        return [f for f in os.listdir(image_dir) if os.path.isfile(os.path.join(image_dir, f))]
    except Exception:
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
            flash(error, "error")
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
         flash("Billede er påkrævet for nye produkter.", "error")
         images = _get_available_images()
         return render_template('admin/product_form.html', product=request.form, images=images)

    try:
        with get_db_connection() as conn:
            with conn.transaction():
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
            
        flash("Produkt gemt.", "success")
        return redirect(url_for('admin.product_list'))

    except Exception as e:
        current_app.logger.error(f"Error saving product: {e}")
        flash("Der opstod en systemfejl ved gemning af produktet.", "error")
        images = _get_available_images()
        return render_template('admin/product_form.html', product=None, images=images) 


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
        flash("Der opstod en fejl ved hentning af produkter.", "error")
        return redirect(url_for('main.index'))

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
            flash("Produktet blev ikke fundet.", "error")
            return redirect(url_for('admin.product_list'))
            
        images = _get_available_images()
        return render_template('admin/product_form.html', product=product, images=images)

    except Exception as e:
        current_app.logger.error(f"Error fetching product {id}: {e}")
        flash("Der opstod en fejl ved hentning af produktet.", "error")
        return redirect(url_for('admin.product_list'))

@bp.route('/products/<int:id>/delete', methods=['POST'])
@admin_required
def product_delete(id):
    try:
        with get_db_connection() as conn:
            with conn.transaction():
                with conn.cursor() as curs:
                    # 1. Check if product is referenced in sales
                    curs.execute("SELECT COUNT(*) FROM sales WHERE productid = %s", (id,))
                    count = curs.fetchone()[0]
                    
                    if count > 0:
                        flash(f"Produktet kan ikke slettes, da det er knyttet til {count} salg. Overvej i stedet at deaktivere det.", "error")
                        return redirect(url_for('admin.product_list'))
                    
                    # 2. Proceed with deletion
                    curs.execute("DELETE FROM products WHERE productid = %s", (id,))
            
        flash("Produkt slettet.", "success")
    except Exception as e:
        current_app.logger.error(f"Error deleting product {id}: {e}")
        flash("Der opstod en fejl ved sletning af produktet.", "error")
        
    return redirect(url_for('admin.product_list'))
