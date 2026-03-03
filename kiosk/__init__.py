
from flask import Flask
from flask_apscheduler import APScheduler
from .config import Config
from .database import init_db, init_db_schema
from .routes import register_routes
from .services.economics import EconomicsService
import logging

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Configure Logging
    logging.basicConfig(level=logging.INFO)
    app.logger.setLevel(logging.INFO)
    logging.getLogger('apscheduler').setLevel(logging.WARNING)

    # Initialize Database
    with app.app_context():
        init_db(app)
        init_db_schema(app)

    # Initialize Scheduler
    scheduler = APScheduler()
    scheduler.init_app(app)
    scheduler.start()

    # Register Scheduler Job
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
