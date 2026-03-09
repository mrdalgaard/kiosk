
from psycopg_pool import ConnectionPool
from psycopg.conninfo import make_conninfo
from .config import Config

import os

def configure_connection(conn):
    # Synchronize PostgreSQL session timezone with the Python server's timezone
    tz = os.environ.get('TZ', 'UTC')
    conn.execute(f"SET TIME ZONE '{tz}'")
    conn.commit()  # Ensure the connection is not left in the INTRANS state

def get_db_pool():
    """
    Creates and returns a connection pool using configuration from the app config 
    or the Config class directly.
    """
    # Create the connection string safely
    conninfo = make_conninfo(
        host=Config.DB_HOST,
        port=Config.DB_PORT,
        dbname=Config.DB_NAME,
        user=Config.DB_USER,
        password=Config.DB_PASSWORD
    )
    return ConnectionPool(conninfo, reconnect_timeout=2, timeout=5.0, configure=configure_connection)

# Global pool instance (initialized in create_app)
pool = None

def init_db(app):
    global pool
    pool = get_db_pool()

def init_db_schema(app):
    """Initializes the database schema from schema.sql and runs any pending migrations."""
    import os
    import time
    
    schema_path = os.path.join(app.root_path, 'schema.sql')
    migrations_dir = os.path.join(app.root_path, 'migrations')
    
    if not os.path.exists(schema_path):
        app.logger.warning(f"Schema file not found at {schema_path}, skipping schema initialization.")
        return

    max_retries = 5
    for attempt in range(max_retries):
        current_migration = None
        try:
            # 1. Run the base schema.sql (this creates tables if they don't exist, including schema_migrations)
            with open(schema_path, 'r') as f:
                schema_sql = f.read()
            
            with get_db_connection() as conn:
                with conn.cursor() as curs:
                    curs.execute(schema_sql)
                conn.commit()
            
            app.logger.info("Base database schema verified.")
            
            # 2. Run Migrations
            if os.path.exists(migrations_dir):
                # Get all .sql files and sort them alphabetically so they run in chronological order
                migration_files = sorted([f for f in os.listdir(migrations_dir) if f.endswith('.sql')])
                
                with get_db_connection() as conn:
                    for filename in migration_files:
                        current_migration = filename
                        # Use a nested transaction for each migration file
                        with conn.transaction():
                            with conn.cursor() as curs:
                                # Check if migration was already applied
                                curs.execute("SELECT version FROM schema_migrations WHERE version = %s", (filename,))
                                if curs.fetchone() is None:
                                    app.logger.info(f"Applying migration: {filename}")
                                    file_path = os.path.join(migrations_dir, filename)
                                    
                                    with open(file_path, 'r') as f:
                                        migration_sql = f.read()
                                    
                                    # Execute the migration script
                                    curs.execute(migration_sql)
                                    
                                    # Mark as completed
                                    curs.execute("INSERT INTO schema_migrations (version) VALUES (%s)", (filename,))
                                    app.logger.info(f"Successfully applied migration: {filename}")
                        current_migration = None
                                
            app.logger.info("Database initialization and migrations completed.")
            return  # Success, exit the function
            
        except Exception as e:
            error_ctx = f" during migration: {current_migration}" if current_migration else ""
            if attempt < max_retries - 1:
                app.logger.warning(f"Database error{error_ctx} (attempt {attempt+1}/{max_retries}): {e}. Retrying in 2 seconds...")
                time.sleep(2)
            else:
                app.logger.error(f"Critical failure{error_ctx} after {max_retries} attempts: {e}")
                raise RuntimeError(f"Database migrations failed to apply{error_ctx}. Application cannot start safely.") from e


def get_db_connection():
    """Helper to get a connection from the global pool"""
    if pool is None:
        raise RuntimeError("Database pool not initialized. Call init_db() first.")
    return pool.connection()
