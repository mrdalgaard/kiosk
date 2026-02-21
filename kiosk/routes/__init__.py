
from functools import wraps
from flask import Blueprint, session, redirect, url_for

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('customerid'):
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated

def register_routes(app):
    from . import auth, main, mowing, api, admin
    
    app.register_blueprint(auth.bp)
    app.register_blueprint(main.bp)
    app.register_blueprint(mowing.bp)
    app.register_blueprint(api.bp)
    app.register_blueprint(admin.bp)
