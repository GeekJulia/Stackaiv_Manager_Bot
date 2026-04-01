import os
from psycopg_pool import ConnectionPool
from dotenv import load_dotenv

load_dotenv()
#test production
DATABASE_URL = (
    f"postgresql://{os.getenv('DB_USER')}:"
    f"{os.getenv('DB_PASSWORD')}@"
    f"{os.getenv('DB_HOST')}:"
    f"{os.getenv('DB_PORT')}/"
    f"{os.getenv('DB_DATABASE')}?sslmode=require"
)

pool = ConnectionPool(
    conninfo=DATABASE_URL,
    min_size=1,
    max_size=20,
    timeout=50,
    max_idle=300,
)
# import os
# import threading
# import logging
# import time
# from psycopg_pool import ConnectionPool
# from dotenv import load_dotenv

# load_dotenv()

# logger = logging.getLogger(__name__)

# DATABASE_URL = (
#     f"postgresql://{os.getenv('DB_USER')}:"
#     f"{os.getenv('DB_PASSWORD')}@"
#     f"{os.getenv('DB_HOST')}:"
#     f"{os.getenv('DB_PORT')}/"
#     f"{os.getenv('DB_DATABASE')}?sslmode=require"
# )

# def create_pool():
#     return ConnectionPool(
#         conninfo=DATABASE_URL,
#         min_size=1,       # ⬇ Reduced - Supabase has connection limits
#         max_size=3,       # ⬇ Reduced - be conservative
#         timeout=30,
#         max_idle=300,     # ⬆ Keep connections longer (5 min)
#         max_lifetime=3600,
#         reconnect_timeout=30,
#         open=False,       # ✅ DON'T block at import time
#         kwargs={
#             "keepalives": 1,
#             "keepalives_idle": 30,
#             "keepalives_interval": 10,
#             "keepalives_count": 5,
#             "connect_timeout": 10,
#         }
#     )

# pool = create_pool()

# def _initialize_pool():
#     """Open pool in background so imports never block or crash."""
#     retries = 0
#     while retries < 10:
#         try:
#             pool.open(wait=True, timeout=30)
#             logger.info("✅ DB pool initialized successfully")
#             return
#         except Exception as e:
#             retries += 1
#             wait = min(5 * retries, 60)
#             logger.warning(f"Pool init attempt {retries} failed: {e}. Retrying in {wait}s...")
#             time.sleep(wait)
#     logger.error("❌ Could not initialize DB pool after 10 attempts")

# def _keep_alive():
#     """Ping DB every 3 minutes. Attempt pool recovery if broken."""
#     global pool
#     while True:
#         time.sleep(180)
#         try:
#             with pool.connection() as conn:
#                 conn.execute("SELECT 1")
#             logger.info("Keep-alive ping successful")
#         except Exception as e:
#             logger.warning(f"Keep-alive failed, attempting pool recovery: {e}")
#             try:
#                 pool.close()
#             except:
#                 pass
#             pool = create_pool()
#             _initialize_pool()

# # Start both threads — neither blocks the import
# threading.Thread(target=_initialize_pool, daemon=True).start()
# threading.Thread(target=_keep_alive, daemon=True).start()