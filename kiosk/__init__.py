
from flask import Flask
from apscheduler.schedulers.background import BackgroundScheduler
from .config import Config
from .database import init_db, init_db_schema
from .routes import register_routes
from .services.economics import EconomicsService
import logging

class ColorFormatter(logging.Formatter):
    """Custom logger formatter that adds color based on level."""
    
    grey = "\x1b[38;20m"
    yellow = "\x1b[33;20m"
    red = "\x1b[31;20m"
    bold_red = "\x1b[31;1m"
    reset = "\x1b[0m"
    
    # We use a standard format string to let super() handle the heavy lifting
    format_str = "[%(asctime)s] [%(process)d] [%(levelname)s] [%(name)s] %(message)s"

    def __init__(self):
        super().__init__(fmt=self.format_str, datefmt="%Y-%m-%d %H:%M:%S %z")

    def format(self, record):
        # Let the base formatter resolve all the built-in variables natively
        formatted = super().format(record)
        
        # Then apply ANSI styling strictly to the resolved string output
        if record.levelno >= logging.ERROR:
            return self.red + formatted + self.reset
        elif record.levelno >= logging.WARNING:
            return self.yellow + formatted + self.reset
        return self.grey + formatted + self.reset

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Configure Logging with Colors
    handler = logging.StreamHandler()
    handler.setFormatter(ColorFormatter())
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, app.config['LOG_LEVEL'], logging.INFO))
    root_logger.handlers = [handler]
    
    app.logger.setLevel(getattr(logging, app.config['LOG_LEVEL'], logging.INFO))
    for app_handler in app.logger.handlers:
        app_handler.setFormatter(ColorFormatter())
        
    logging.getLogger('apscheduler').setLevel(getattr(logging, app.config['SCHEDULER_LOG_LEVEL'], logging.WARNING))

    # Initialize Database
    with app.app_context():
        init_db(app)
        init_db_schema(app)

    # Initialize Scheduler (using raw APScheduler instead of Flask-APScheduler)
    if app.config.get('ENABLE_ECONOMICS', True):
        scheduler = BackgroundScheduler(daemon=True)

        def transfer_to_economics_job():
            with app.app_context():
                EconomicsService.sync_pending_transfers()

        def update_users_job():
            with app.app_context():
                try:
                    EconomicsService.update_users()
                except Exception as e:
                    app.logger.warning(f"Background user sync failed: {e}")

        scheduler.add_job(transfer_to_economics_job, 'interval', id="transferEco", seconds=30, coalesce=True, max_instances=1)
        scheduler.add_job(update_users_job, 'interval', id="updateUsersEco", minutes=30, coalesce=True, max_instances=1)

        scheduler.start()
        app.scheduler = scheduler  # Keep reference to prevent GC

    # Register Routes
    register_routes(app)
    
    from flask import session
    @app.context_processor
    def inject_admin_status():
        def is_admin():
            customer_id = session.get('customerid')
            return customer_id and customer_id in Config.ADMIN_USER_IDS
        return dict(is_admin=is_admin)

    @app.after_request
    def add_security_headers(response):
        # Prevent HTML pages from being cached/stored to protect sensitive data on back-button
        if response.mimetype == 'text/html':
            response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
            response.headers['Pragma'] = 'no-cache'
            response.headers['Expires'] = '0'
            response.headers['Vary'] = 'Cookie'
        return response

    return app
