from flask import Blueprint, render_template, request, redirect, url_for, session, current_app, flash
from ...database import get_db_connection
import psycopg
import time
import threading

bp = Blueprint('admin', __name__, url_prefix='/admin')

# PIN brute-force protection: track failed attempts per IP
_pin_attempts = {}  # {ip: (fail_count, last_fail_timestamp)}
_pin_lock = threading.Lock()

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
             flash("Du har ikke adgang til admin-panelet.", "error")
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
            return redirect(url_for('admin.index'))
        else:
            with _pin_lock:
                _pin_attempts[ip] = (fail_count + 1, time.monotonic())
            return render_template('admin/login.html', error="Forkert PIN kode")
    
    return render_template('admin/login.html')

@bp.route('/')
@admin_required
def index():
    return render_template('admin/index.html')

# Import modules so the routes are registered on the blueprint
from . import products, images, mowing_users, mowing_sections, mowing_maintenance
