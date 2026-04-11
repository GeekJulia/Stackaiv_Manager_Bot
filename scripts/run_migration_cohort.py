import os
from dotenv import load_dotenv
from psycopg_pool import ConnectionPool

load_dotenv()
conninfo = f"dbname='{os.getenv('DB_DATABASE')}' user='{os.getenv('DB_USER')}' password='{os.getenv('DB_PASSWORD')}' host='{os.getenv('DB_HOST')}' port='{os.getenv('DB_PORT')}'"
pool = ConnectionPool(conninfo=conninfo)

with pool.connection() as conn:
    with conn.cursor() as cur:
        with open('scripts/migration_cohort.sql', 'r') as f:
            cur.execute(f.read())
        conn.commit()
        print('Migration cohort executed successfully.')
