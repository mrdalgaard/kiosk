from flask import render_template, request, redirect, url_for, flash, current_app
from werkzeug.utils import secure_filename
import os
from ...database import get_db_connection
from . import bp, admin_required
from .utils import _validate_image

@bp.route('/images')
@admin_required
def image_gallery():
    image_dir = os.path.join(current_app.root_path, 'static', 'images')
    try:
        if not os.path.exists(image_dir):
            current_app.logger.error(f"Image directory does not exist: {image_dir}")
            flash("Billedmappen findes ikke.", "error")
            images = []
        elif not os.access(image_dir, os.R_OK | os.X_OK):
            current_app.logger.error(f"Permission denied for image directory: {image_dir}")
            flash("Systemet har ikke adgang til at læse billedmappen.", "error")
            images = []
        else:
            images = [f for f in os.listdir(image_dir) if os.path.isfile(os.path.join(image_dir, f))]
            images.sort()
    except Exception as e:
        current_app.logger.error(f"Unexpected error reading image directory: {e}")
        images = []
        flash("Der opstod en fejl ved læsning af billedmappen.", "error")
    
    return render_template('admin/image_gallery.html', images=images)

@bp.route('/images/upload', methods=['POST'])
@admin_required
def image_upload():
    image_file = request.files.get('imagefile')
    if image_file and image_file.filename:
        ok, error = _validate_image(image_file)
        if not ok:
            flash(error, "error")
            return redirect(url_for('admin.image_gallery'))
        filename = secure_filename(image_file.filename)
        save_path = os.path.join(current_app.root_path, 'static', 'images', filename)
        try:
            image_file.save(save_path)
            flash(f"Billede '{filename}' uploadet.", "success")
        except PermissionError:
            current_app.logger.error(f"Permission denied when saving image to {save_path}")
            flash("Systemet har ikke skriveadgang til billedmappen. Kontakt administratoren.", "error")
        except Exception as e:
            current_app.logger.error(f"Error saving image: {e}")
            flash("Der opstod en fejl ved gemning af billedet.", "error")
    else:
        flash("Ingen fil valgt.", "error")
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
            flash(f"Billedet '{filename}' bruges af {count} produkt(er) og kan ikke slettes.", "error")
        else:
            if os.path.exists(image_path):
                os.remove(image_path)
                flash(f"Billede '{filename}' slettet.", "success")
            else:
                flash("Filen findes ikke.", "error")
    except Exception as e:
        current_app.logger.error(f"Error deleting image: {e}")
        flash("Der opstod en fejl ved sletning af billedet.", "error")
        
    return redirect(url_for('admin.image_gallery'))
