from flask import current_app

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
