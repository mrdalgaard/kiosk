
from flask import Flask
from flask_apscheduler import APScheduler
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
    format_str = "%(levelname)s:%(name)s:%(message)s"

    def __init__(self):
        super().__init__(fmt=self.format_str)

    FORMATS = {
        logging.DEBUG: grey + format_str + reset,
        logging.INFO: grey + format_str + reset,
        logging.WARNING: yellow + format_str + reset,
        logging.ERROR: red + format_str + reset,
        logging.CRITICAL: bold_red + format_str + reset
    }

    def format(self, record):
        formatted = super().format(record)
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

    # Initialize Scheduler
    scheduler = APScheduler()
    scheduler.init_app(app)
    scheduler.start()

    # Register Scheduler Job
    if app.config.get('ENABLE_ECONOMICS', True):
        @scheduler.task("interval", id="transferEco", seconds=30, coalesce=True, max_instances=1)
        def transfer_to_economics_job():
            with app.app_context():
                EconomicsService.sync_pending_transfers()

        # Register Periodic User Sync Job
        @scheduler.task("interval", id="updateUsersEco", minutes=30, coalesce=True, max_instances=1)
        def update_users_job():
            with app.app_context():
                try:
                    EconomicsService.update_users()
                except Exception as e:
                    app.logger.warning(f"Background user sync failed: {e}")

    # Register Routes
    register_routes(app)
    
    from flask import session
    @app.context_processor
    def inject_admin_status():
        def is_admin():
            customer_id = session.get('customerid')
            return customer_id and customer_id in Config.ADMIN_USER_IDS
        return dict(is_admin=is_admin)

    return app
