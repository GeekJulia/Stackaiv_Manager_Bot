import psycopg
from app.database.clients import pool
import sys

try:
    with pool.connection() as conn:
        with conn.cursor() as cur:
            # Check for duplicates
            cur.execute("""
                SELECT created_by, COUNT(*) 
                FROM programs 
                GROUP BY created_by 
                HAVING COUNT(*) > 1;
            """)
            dups = cur.fetchall()
            if dups:
                print("Duplicates found:", dups)
                for created_by, count in dups:
                    print(f"Resolving duplicate for created_by {created_by}...")
                    cur.execute(f"DELETE FROM programs WHERE created_by = {created_by} AND id NOT IN (SELECT min(id) FROM programs WHERE created_by = {created_by})")
            
            # Add constraint
            try:
                cur.execute("ALTER TABLE programs ADD CONSTRAINT programs_created_by_key UNIQUE (created_by);")
                print("Added unique constraint.")
            except Exception as e:
                print("Constraint might already exist or failed:", e)
            conn.commit()
except Exception as e:
    print("Error:", e)
    sys.exit(1)
