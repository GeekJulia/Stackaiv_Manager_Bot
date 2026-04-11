import os
from dotenv import load_dotenv
from psycopg_pool import ConnectionPool

load_dotenv()
pool = ConnectionPool(conninfo=f"dbname='{os.getenv('DB_DATABASE')}' user='{os.getenv('DB_USER')}' password='{os.getenv('DB_PASSWORD')}' host='{os.getenv('DB_HOST')}' port='{os.getenv('DB_PORT')}'")

with pool.connection() as conn:
    with conn.cursor() as cur:
        cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS program_id INTEGER REFERENCES programs(id);")
        conn.commit()
        print("Migration successful: added program_id to users.")
