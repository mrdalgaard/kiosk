
from psycopg_pool import ConnectionPool
from psycopg.conninfo import make_conninfo
from .config import Config

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
    return ConnectionPool(conninfo, reconnect_timeout=2, timeout=5.0)

# Global pool instance (initialized in create_app)
pool = None

def init_db(app):
    global pool
    pool = get_db_pool()

def init_db_schema(app):
    """Initializes the database schema from schema.sql"""
    import os
    
    schema_path = os.path.join(app.root_path, 'schema.sql')
    
    if not os.path.exists(schema_path):
        app.logger.warning(f"Schema file not found at {schema_path}, skipping schema initialization.")
        return

    import time
    
    max_retries = 5
    for attempt in range(max_retries):
        try:
            with open(schema_path, 'r') as f:
                schema_sql = f.read()
            
            with get_db_connection() as conn:
                with conn.cursor() as curs:
                    curs.execute(schema_sql)
                        
                conn.commit()
                
            app.logger.info("Database schema initialized successfully.")
            return  # Success, exit the function
        except Exception as e:
            if attempt < max_retries - 1:
                app.logger.warning(f"Database not ready yet (attempt {attempt+1}/{max_retries}): {e}. Retrying in 2 seconds...")
                time.sleep(2)
            else:
                app.logger.error(f"Failed to initialize database schema after {max_retries} attempts: {e}")


def get_db_connection():
    """Helper to get a connection from the global pool"""
    if pool is None:
        raise RuntimeError("Database pool not initialized. Call init_db() first.")
    return pool.connection()
