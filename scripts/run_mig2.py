import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.database.clients import pool

with pool.connection() as conn:
    with conn.cursor() as cur:
        with open('scripts/migration_cohort.sql', 'r') as f:
            cur.execute(f.read())
        conn.commit()
        print('Migration cohort executed successfully.')
