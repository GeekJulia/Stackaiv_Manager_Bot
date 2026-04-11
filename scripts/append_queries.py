APPEND_CODE = """
def promote_program(program_id):
    \"\"\"Bumps up the active level sequence of a program by 100 dynamically\"\"\"
    with pool.connection() as conn:
        with conn.cursor() as cursor:
            try:
                cursor.execute(\"\"\"
                    UPDATE programs
                    SET level = (CAST(NULLIF(REGEXP_REPLACE(level, '\D', '', 'g'), '') AS INTEGER) + 100)::text || ' Level'
                    WHERE id = %s
                    RETURNING level
                \"\"\", (program_id,))
                conn.commit()
                res = cursor.fetchone()
                return res[0] if res else None
            except Exception as e:
                print(f"ERROR: promote_program failed - {str(e)}")
                return None

def check_archive_access(user_id, target_level=None, target_course_id=None):
    \"\"\"Validates multi-tiered access matrix\"\"\"
    with pool.connection() as conn:
        with conn.cursor() as cursor:
            # Bypass lifetime access
            cursor.execute("SELECT id FROM archive_subscriptions WHERE user_id=%s AND access_type='full' LIMIT 1", (user_id,))
            if cursor.fetchone(): return True
            
            # Specific level access
            if target_level:
                cursor.execute("SELECT id FROM archive_subscriptions WHERE user_id=%s AND access_type='level' AND target_level=%s LIMIT 1", (user_id, target_level))
                if cursor.fetchone(): return True
                
            # Specific course access
            if target_course_id:
                cursor.execute("SELECT id FROM archive_subscriptions WHERE user_id=%s AND access_type='course' AND target_course_id=%s LIMIT 1", (user_id, target_course_id))
                if cursor.fetchone(): return True
                
            return False
"""

with open('app/database/queries.py', 'a') as f:
    f.write(APPEND_CODE)
