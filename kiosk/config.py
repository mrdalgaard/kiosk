import os
import secrets

class Config:
    # Use environment variable, fallback to a random key per startup
    DEBUG = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    SECRET_KEY = os.environ.get('SECRET_KEY') or secrets.token_hex(32)
    
    # Database configuration
    DB_HOST = os.environ.get('DB_HOST', 'postgres')
    DB_PORT = os.environ.get('DB_PORT', '5432')
    DB_NAME = os.environ.get('DB_NAME', 'KantinePOS')
    DB_USER = os.environ.get('DB_USER', 'KantinePOS')
    
    DB_PASSWORD = os.environ.get('DB_PASSWORD')
    if not DB_PASSWORD:
        raise ValueError("No DB_PASSWORD set for Flask application")
    
    # Economics API
    ECO_GRANT_TOKEN = os.environ.get('ECO_GRANT_TOKEN')
    ECO_SECRET_TOKEN = os.environ.get('ECO_SECRET_TOKEN')

    if not ECO_GRANT_TOKEN or not ECO_SECRET_TOKEN:
        raise ValueError("No Economics API tokens set for Flask application")

    ECO_PRODUCT_ID = int(os.environ.get('ECO_PRODUCT_ID', 8000))
    ECO_MAX_ATTEMPTS = 4
    ECO_MIN_CUSTOMER_REFRESH_INTERVAL_SEC = 60
    
    # Admin Settings
    ADMIN_USER_IDS = [int(x) for x in os.environ.get('ADMIN_USER_IDS', '').split(',') if x.strip()]
    ADMIN_PIN = os.environ.get('ADMIN_PIN', '1234')  # Default PIN: 1234
    ADMIN_PIN_MAX_ATTEMPTS = 5
    ADMIN_PIN_LOCKOUT_SECONDS = 60
    
    # App Settings
    # Cache static files: 0s in dev, else fallback to 1 hour
    SEND_FILE_MAX_AGE_DEFAULT = int(os.environ.get('SEND_FILE_MAX_AGE_DEFAULT', 0 if DEBUG else 3600))
    CUSTOMER_GROUPS = [10, 15, 20, 30, 40]
    CUSTOMER_GROUPS_ALL = [1] + CUSTOMER_GROUPS  # Group 1 is hidden but active

    # Image Upload
    ALLOWED_IMAGE_EXTENSIONS = {'jpg', 'jpeg', 'png', 'gif', 'webp', 'svg', 'bmp', 'ico'}
    MAX_IMAGE_SIZE_BYTES = 100 * 1024  # 100 KB
