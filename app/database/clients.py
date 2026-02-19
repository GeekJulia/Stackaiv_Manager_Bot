import os
import threading
import logging
from psycopg_pool import ConnectionPool
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

DATABASE_URL = (
    f"postgresql://{os.getenv('DB_USER')}:"
    f"{os.getenv('DB_PASSWORD')}@"
    f"{os.getenv('DB_HOST')}:"
    f"{os.getenv('DB_PORT')}/"
    f"{os.getenv('DB_DATABASE')}?sslmode=require"
)

pool = ConnectionPool(
    conninfo=DATABASE_URL,
    min_size=2,
    max_size=10,
    timeout=25,
    max_idle=60,
    max_lifetime=600,
    reconnect_timeout=10,
    kwargs={
        "keepalives": 1,
        "keepalives_idle": 30,
        "keepalives_interval": 10,
        "keepalives_count": 5,
    }
)

# Eagerly open connections FIRST so pool is ready before thread starts
pool.wait(timeout=30)

def _keep_alive():
    """Ping the database every 3 minutes to prevent cold connections."""
    while True:
        try:
            with pool.connection() as conn:
                conn.execute("SELECT 1")
            logger.info("Keep-alive ping successful")
        except Exception as e:
            logger.warning(f"Keep-alive ping failed: {e}")
        threading.Event().wait(180)

_ka_thread = threading.Thread(target=_keep_alive, daemon=True)
_ka_thread.start()