import os
import psycopg # type: ignore
from dotenv import load_dotenv
from .clients import pool

# Load environment variables
load_dotenv()

def ensure_schema():
    try:
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS program_id INTEGER REFERENCES programs(id);")
                # Cohort migrations
                cur.execute("ALTER TABLE programs ADD COLUMN IF NOT EXISTS graduation_year INTEGER;")
                cur.execute("ALTER TABLE courses ADD COLUMN IF NOT EXISTS semester VARCHAR(20) DEFAULT 'Alpha';")
                cur.execute("ALTER TABLE courses ADD COLUMN IF NOT EXISTS academic_level VARCHAR(20);")
                cur.execute("""
                    UPDATE courses c
                    SET academic_level = p.level
                    FROM programs p
                    WHERE c.program_id = p.id AND c.academic_level IS NULL;
                """)
                cur.execute("""
                CREATE TABLE IF NOT EXISTS archive_subscriptions (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                    access_type VARCHAR(20) NOT NULL,
                    target_course_id INTEGER REFERENCES courses(id) ON DELETE CASCADE,
                    target_level VARCHAR(20),
                    payment_reference VARCHAR(100) UNIQUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """)
                # Evolution of payments table
                cur.execute("ALTER TABLE payments ADD COLUMN IF NOT EXISTS payment_type VARCHAR(50) DEFAULT 'hub_activation';")
                cur.execute("ALTER TABLE payments ADD COLUMN IF NOT EXISTS metadata JSONB;")
                conn.commit()
    except Exception as e:
        print(f"Schema migration error (ignored): {e}")

# Run schema migrations automatically
ensure_schema()

# -------------------------
# Save or Update Telegram User
# -------------------------
def save_user(telegram_id, username, first_name, career=None):
    try:
        with pool.connection() as conn:
            with conn.cursor() as cursor:
                # Use a try-except block just in case the migration hasn't run yet
                try:
                    query = """
                    INSERT INTO users (telegram_id, username, first_name, career)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (telegram_id) DO UPDATE
                    SET username = EXCLUDED.username,
                        first_name = EXCLUDED.first_name,
                        career = COALESCE(EXCLUDED.career, users.career)
                    RETURNING id;
                    """
                    cursor.execute(query, (telegram_id, username, first_name, career))
                except psycopg.errors.UndefinedColumn:
                    # Fallback if career column doesn't exist yet
                    conn.rollback()
                    query = """
                    INSERT INTO users (telegram_id, username, first_name)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (telegram_id) DO UPDATE
                    SET username = EXCLUDED.username,
                        first_name = EXCLUDED.first_name
                    RETURNING id;
                    """
                    cursor.execute(query, (telegram_id, username, first_name))
                
                conn.commit()
                return cursor.fetchone()[0]
    except Exception as e:
        print(f"ERROR: save_user failed - {str(e)}")
        raise

# -------------------------
# Save Program Registration
# -------------------------
def get_user_info_by_telegram_id(telegram_id):
    """Get basic user info from the users table"""
    with pool.connection() as conn:
        with conn.cursor() as cursor:
            try:
                cursor.execute("""
                    SELECT id, username, first_name, career
                    FROM users
                    WHERE telegram_id = %s
                """, (telegram_id,))
                r = cursor.fetchone()
                if r:
                    return {
                        "id": r[0],
                        "username": r[1],
                        "first_name": r[2],
                        "career": r[3]
                    }
            except psycopg.errors.UndefinedColumn:
                # Fallback if career column doesn't exist yet
                conn.rollback()
                cursor.execute("""
                    SELECT id, username, first_name
                    FROM users
                    WHERE telegram_id = %s
                """, (telegram_id,))
                r = cursor.fetchone()
                if r:
                    return {
                        "id": r[0],
                        "username": r[1],
                        "first_name": r[2],
                        "career": None
                    }
            return None


def save_program(level, college, program_name, user_id, graduation_year):
    try:
        with pool.connection() as conn:
            with conn.cursor() as cursor:
                query = """
                INSERT INTO programs (level, college, name, created_by, graduation_year)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (created_by) DO UPDATE
                SET is_active = CASE 
                        WHEN programs.graduation_year != EXCLUDED.graduation_year OR 
                             programs.college != EXCLUDED.college OR 
                             programs.name != EXCLUDED.name 
                        THEN FALSE 
                        ELSE programs.is_active 
                    END,
                    level = EXCLUDED.level,
                    college = EXCLUDED.college,
                    name = EXCLUDED.name,
                    graduation_year = EXCLUDED.graduation_year
                RETURNING id;
                """
                cursor.execute(query, (level, college, program_name, user_id, graduation_year))
                conn.commit()
                return cursor.fetchone()[0]
    except Exception as e:
        print(f"ERROR: save_program failed - {str(e)}")
        raise
    
def get_user_program_id(telegram_id):
    """Get active program ID for a user. First checks if they are linked to one, then if they created one."""
    with pool.connection() as conn:
        with conn.cursor() as cursor:
            # First check if user is linked via program_id
            try:
                cursor.execute("SELECT program_id FROM users WHERE telegram_id = %s", (telegram_id,))
                res = cursor.fetchone()
                if res and res[0]:
                    return res[0]
            except Exception:
                pass # column might not exist yet if DB is mid-migration
            
            # Fallback to created_by if no linkage (backward compatibility)
            cursor.execute("""
                SELECT p.id
                FROM programs p
                JOIN users u ON p.created_by = u.id
                WHERE u.telegram_id = %s
            """, (telegram_id,))
            result = cursor.fetchone()
            return result[0] if result else None

def link_user_to_program(telegram_id, program_id):
    """Link a user to a specific program directly via the users table."""
    try:
        with pool.connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    UPDATE users 
                    SET program_id = %s 
                    WHERE telegram_id = %s
                """, (program_id, telegram_id))
                conn.commit()
                return True
    except Exception as e:
        print(f"ERROR: link_user_to_program failed - {str(e)}")
        return False

def user_has_program(telegram_id):
    """Check if a user already has a registered program"""
    return get_user_program_id(telegram_id) is not None

def get_user_program_info(telegram_id):
    """Get full program information for a user"""
    program_id = get_user_program_id(telegram_id)
    if program_id:
        return get_program_info(program_id, include_user_id=False)
    return None


def save_courses(program_id, course_codes, academic_level, semester='Alpha'):
    if not course_codes:
        return []
    
    try:
        # Batch insert utilizing ON CONFLICT to avoid sequential N+1 database querying.
        placeholders = ", ".join(["(%s, %s, %s, %s)"] * len(course_codes))
        
        flat_values = []
        for code in course_codes:
            flat_values.extend([program_id, code, academic_level, semester])
            
        with pool.connection() as conn:
            with conn.cursor() as cursor:
                query = f"""
                    INSERT INTO courses (program_id, course_code, academic_level, semester)
                    VALUES {placeholders}
                    ON CONFLICT (program_id, course_code) DO UPDATE
                    SET course_code = EXCLUDED.course_code,
                        academic_level = EXCLUDED.academic_level,
                        semester = EXCLUDED.semester
                    RETURNING id;
                """
                cursor.execute(query, flat_values)
                results = cursor.fetchall()
                conn.commit()
                return [r[0] for r in results]
    except Exception as e:
        print(f"ERROR: save_courses failed - {str(e)}")
        raise

def remove_duplicate_courses(program_id):
    """Remove duplicate course codes for a program, keeping only the first occurrence"""
    with pool.connection() as conn:
        with conn.cursor() as cursor:
            # Find and delete duplicates, keeping the oldest (lowest ID)
            cursor.execute("""
                DELETE FROM courses
                WHERE id IN (
                    SELECT id
                    FROM (
                        SELECT id,
                               ROW_NUMBER() OVER (PARTITION BY program_id, course_code ORDER BY id) AS rn
                        FROM courses
                        WHERE program_id = %s
                    ) t
                    WHERE t.rn > 1
                )
            """, (program_id,))
            conn.commit()
            return cursor.rowcount  # Returns number of duplicates removed


def get_resource_types():
    with pool.connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id, name FROM resource_types")
            return [{"id": r[0], "name": r[1]} for r in cursor.fetchall()]


def save_course_resource_types(course_id, resource_type_ids):
    if not resource_type_ids:
        return
        
    try:
        placeholders = ", ".join(["(%s, %s)"] * len(resource_type_ids))
        
        flat_values = []
        for r_id in resource_type_ids:
            flat_values.extend([course_id, r_id])
            
        with pool.connection() as conn:
            with conn.cursor() as cursor:
                query = f"""
                    INSERT INTO course_resource_types (course_id, resource_type_id)
                    VALUES {placeholders}
                    ON CONFLICT DO NOTHING;
                """
                cursor.execute(query, flat_values)
                conn.commit()
    except Exception as e:
        print(f"ERROR: save_course_resource_types failed - {str(e)}")
        raise

def get_courses_by_program(program_id, academic_level=None, semester=None):
    """Fetch courses for a program, optionally filtered by level and semester."""
    with pool.connection() as conn:
        with conn.cursor() as cursor:
            query = "SELECT id, course_code, semester FROM courses WHERE program_id = %s"
            params = [program_id]
            
            if academic_level:
                query += " AND academic_level = %s"
                params.append(academic_level)
            if semester:
                query += " AND semester = %s"
                params.append(semester)
                
            query += " ORDER BY course_code"
            cursor.execute(query, params)
            return [{"id": r[0], "course_code": r[1], "semester": r[2]} for r in cursor.fetchall()]


def save_resource(course_id, resource_type_id, file_id, file_name, uploader_id):
    with pool.connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO resources (course_id, resource_type_id, file_id, file_name, uploader_id)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (file_id) DO NOTHING
                RETURNING id
            """, (course_id, resource_type_id, file_id, file_name, uploader_id))
            conn.commit()
            result = cursor.fetchone()
            return result[0] if result else None


def get_resources_by_course_and_type(course_id, resource_type_id):
    with pool.connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT file_id, file_name
                FROM resources
                WHERE course_id = %s AND resource_type_id = %s
                ORDER BY created_at
            """, (course_id, resource_type_id))
            return [{"file_id": r[0], "file_name": r[1]} for r in cursor.fetchall()]

def get_all_resources_by_course(course_id):
    with pool.connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT file_id, file_name
                FROM resources
                WHERE course_id = %s
                ORDER BY created_at
            """, (course_id,))
            return [{"file_id": r[0], "file_name": r[1]} for r in cursor.fetchall()]
    
def get_course_info(course_id):
    with pool.connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT id, course_code
                FROM courses
                WHERE id = %s
            """, (course_id,))
            r = cursor.fetchone()
            if r:
                return {"id": r[0], "course_code": r[1]}
            return None

# -------------------------
# NEW FUNCTIONS FOR START.PY
# -------------------------

def check_program_exists(college, program_name, graduation_year):
    """Check if a program cohort already exists in the database"""
    with pool.connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT id, level, college, name, created_by, graduation_year
                FROM programs
                WHERE LOWER(college) = LOWER(%s) 
                  AND LOWER(name) = LOWER(%s)
                  AND graduation_year = %s
                LIMIT 1
            """, (college, program_name, graduation_year))
            r = cursor.fetchone()
            if r:
                return {
                    "id": r[0],
                    "level": r[1],
                    "college": r[2],
                    "program_name": r[3],
                    "user_id": r[4],
                    "graduation_year": r[5]
                }
            return None

def get_program_creator(program_id):
    """Get the user who created a specific program"""
    with pool.connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT u.id, u.telegram_id, u.username, u.first_name
                FROM users u
                JOIN programs p ON p.created_by = u.id
                WHERE p.id = %s
            """, (program_id,))
            r = cursor.fetchone()
            if r:
                return {
                    "id": r[0],
                    "telegram_id": r[1],
                    "username": r[2],
                    "first_name": r[3]
                }
            return None

def get_program_info(program_id, include_user_id=False):
    """Get program information by program ID
    
    Args:
        program_id: The program ID to fetch
        include_user_id: If True, includes user_id (created_by) in the result
    
    Returns:
        Dictionary with program info: id, level, college, program_name, and optionally user_id
    """
    with pool.connection() as conn:
        with conn.cursor() as cursor:
            if include_user_id:
                cursor.execute("""
                    SELECT id, level, college, name, created_by
                    FROM programs
                    WHERE id = %s
                """, (program_id,))
            else:
                cursor.execute("""
                    SELECT id, level, college, name
                    FROM programs
                    WHERE id = %s
                """, (program_id,))
            r = cursor.fetchone()
            if r:
                result = {
                    "id": r[0],
                    "level": r[1],
                    "college": r[2],
                    "program_name": r[3]
                }
                if include_user_id and len(r) > 4:
                    result["user_id"] = r[4]
                return result
            return None

def clear_user_program_data(program_id):
    """Clear all courses and resource types associated with a program (FULL WIPE)"""
    with pool.connection() as conn:
        with conn.cursor() as cursor:
            # 1. Delete all course_resource_types for courses in this program
            cursor.execute("""
                DELETE FROM course_resource_types 
                WHERE course_id IN (
                    SELECT id FROM courses WHERE program_id = %s
                )
            """, (program_id,))
            
            # 2. Delete all resources for courses in this program
            cursor.execute("""
                DELETE FROM resources 
                WHERE course_id IN (
                    SELECT id FROM courses WHERE program_id = %s
                )
            """, (program_id,))
            
            # 3. Delete all courses for this program
            cursor.execute("""
                DELETE FROM courses WHERE program_id = %s
            """, (program_id,))
            
            conn.commit()
            return True

def clear_semester_data(program_id, semester):
    """Clear all courses and resources associated with a specific semester in a program"""
    try:
        with pool.connection() as conn:
            with conn.cursor() as cursor:
                # 1. Delete resource types for courses in this semester
                cursor.execute("""
                    DELETE FROM course_resource_types 
                    WHERE course_id IN (
                        SELECT id FROM courses WHERE program_id = %s AND semester = %s
                    )
                """, (program_id, semester))
                
                # 2. Delete resources for courses in this semester
                cursor.execute("""
                    DELETE FROM resources 
                    WHERE course_id IN (
                        SELECT id FROM courses WHERE program_id = %s AND semester = %s
                    )
                """, (program_id, semester))
                
                # 3. Delete courses for this semester
                cursor.execute("""
                    DELETE FROM courses WHERE program_id = %s AND semester = %s
                """, (program_id, semester))
                
                conn.commit()
                return True
    except Exception as e:
        print(f"ERROR: clear_semester_data failed - {str(e)}")
        return False

# -------------------------
# GROUP MANAGEMENT FUNCTIONS
# -------------------------

# Note: get_program_by_id is deprecated - use get_program_info instead
def get_program_by_id(program_id):
    """Get program details by program ID (deprecated - use get_program_info instead)"""
    result = get_program_info(program_id, include_user_id=False)
    if result:
        # Maintain backward compatibility by adding 'name' field
        result['name'] = result['program_name']
    return result

def save_group(telegram_chat_id, program_id):
    """Save or update group chat with program ID"""
    try:
        with pool.connection() as conn:
            with conn.cursor() as cursor:
                query = """
                INSERT INTO groups (telegram_chat_id, program_id)
                VALUES (%s, %s)
                ON CONFLICT (telegram_chat_id) DO UPDATE
                SET program_id = EXCLUDED.program_id
                RETURNING id;
                """
                cursor.execute(query, (telegram_chat_id, program_id))
                conn.commit()
                return cursor.fetchone()[0]
    except Exception as e:
        print(f"ERROR: save_group failed - {str(e)}")
        raise

def get_group_program_id(telegram_chat_id):
    """Get program ID for a group chat"""
    with pool.connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT program_id
                FROM groups
                WHERE telegram_chat_id = %s
            """, (telegram_chat_id,))
            result = cursor.fetchone()
            return result[0] if result else None

def check_duplicate_resource(course_id, resource_type_id, file_name):
    """Check if a resource with the same filename already exists"""
    with pool.connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT COUNT(*)
                FROM resources
                WHERE course_id = %s 
                AND resource_type_id = %s 
                AND file_name = %s
            """, (course_id, resource_type_id, file_name))
            count = cursor.fetchone()[0]
            return count > 0

def save_approval(resource_id, approved_by_telegram_id):
    """Save approval record"""
    with pool.connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO approvals (resource_id, approved_by)
                VALUES (%s, %s)
            """, (resource_id, approved_by_telegram_id))
            conn.commit()

# -------------------------
# PAYMENT & ACTIVATION FUNCTIONS
# -------------------------

def save_payment(program_id, reference, amount, status, payment_type='hub_activation', metadata=None):
    """Save payment transaction record"""
    import json
    metadata_json = json.dumps(metadata) if metadata else None
    try:
        with pool.connection() as conn:
            with conn.cursor() as cursor:
                query = """
                INSERT INTO payments (program_id, reference, amount, status, payment_type, metadata)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (reference) DO UPDATE
                SET status = EXCLUDED.status,
                    metadata = COALESCE(EXCLUDED.metadata, payments.metadata)
                RETURNING id;
                """
                cursor.execute(query, (program_id, reference, amount, status, payment_type, metadata_json))
                conn.commit()
                result = cursor.fetchone()[0]
                return result
    except Exception as e:
        print(f"ERROR: save_payment failed - {str(e)}")
        raise

def save_archive_subscription(user_id, access_type, target_id=None, target_level=None, reference=None):
    """Fulfill an archive subscription payment"""
    with pool.connection() as conn:
        with conn.cursor() as cursor:
            # Check for existing record to avoid duplicates
            cursor.execute("SELECT id FROM archive_subscriptions WHERE payment_reference = %s", (reference,))
            if cursor.fetchone(): return True
            
            cursor.execute("""
                INSERT INTO archive_subscriptions (user_id, access_type, target_course_id, target_level, payment_reference)
                VALUES (%s, %s, %s, %s, %s)
            """, (user_id, access_type, target_id if access_type == 'course' else None, target_level, reference))
            conn.commit()
            return True

def get_payment_by_reference(reference):
    """Get payment record by Paystack reference"""
    try:
        with pool.connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT id, program_id, reference, amount, status
                    FROM payments
                    WHERE reference = %s
                """, (reference,))
                r = cursor.fetchone()
                if r:
                    result = {
                        "id": r[0],
                        "program_id": r[1],
                        "reference": r[2],
                        "amount": r[3],
                        "status": r[4]
                    }
                    print(f"DEBUG: Payment found - {result}")
                    return result
                else:
                    print(f"DEBUG: Payment not found for reference={reference}")
                    return None
    except Exception as e:
        print(f"ERROR: get_payment_by_reference failed - {str(e)}")
        raise
        return None

def activate_program(program_id, is_paid=True):
    """Mark program as active and create activation record
    
    Args:
        program_id: The program to activate
        is_paid: Whether this activation was paid (True) or free (False)
    """
    with pool.connection() as conn:
        with conn.cursor() as cursor:
            # Update program is_active status
            cursor.execute("""
                UPDATE programs
                SET is_active = TRUE
                WHERE id = %s
            """, (program_id,))
            
            # Create activation record
            cursor.execute("""
                INSERT INTO program_activations (program_id, is_paid)
                VALUES (%s, %s)
            """, (program_id, is_paid))
            
            conn.commit()
            return True

def get_program_activation_status(program_id):
    """Check if a program is active"""
    with pool.connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT is_active
                FROM programs
                WHERE id = %s
            """, (program_id,))
            r = cursor.fetchone()
            return r[0] if r else False

def get_all_programs():
    """Get all registered programs"""
    with pool.connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT p.id, p.level, p.college, p.name, p.created_by, p.is_active, u.first_name, u.username
                FROM programs p
                JOIN users u ON p.created_by = u.id
                ORDER BY p.created_at DESC
            """)
            return [
                {
                    "id": r[0],
                    "level": r[1],
                    "college": r[2],
                    "name": r[3],
                    "created_by": r[4],
                    "is_active": r[5],
                    "creator_name": r[6],
                    "creator_username": r[7]
                }
                for r in cursor.fetchall()
            ]

def delete_program(program_id):
    """Delete a program and all related data"""
    with pool.connection() as conn:
        with conn.cursor() as cursor:
            # Delete approvals
            cursor.execute("""
                DELETE FROM approvals 
                WHERE resource_id IN (
                    SELECT id FROM resources WHERE course_id IN (
                        SELECT id FROM courses WHERE program_id = %s
                    )
                )
            """, (program_id,))
            
            # Delete resources
            cursor.execute("""
                DELETE FROM resources 
                WHERE course_id IN (
                    SELECT id FROM courses WHERE program_id = %s
                )
            """, (program_id,))
            
            # Delete course_resource_types
            cursor.execute("""
                DELETE FROM course_resource_types 
                WHERE course_id IN (
                    SELECT id FROM courses WHERE program_id = %s
                )
            """, (program_id,))
            
            # Delete courses
            cursor.execute("""
                DELETE FROM courses WHERE program_id = %s
            """, (program_id,))
            
            # Delete groups
            cursor.execute("""
                DELETE FROM groups WHERE program_id = %s
            """, (program_id,))
            
            # Delete payments
            cursor.execute("""
                DELETE FROM payments WHERE program_id = %s
            """, (program_id,))
            
            # Delete activations
            cursor.execute("""
                DELETE FROM program_activations WHERE program_id = %s
            """, (program_id,))
            
            # Delete program
            cursor.execute("""
                DELETE FROM programs WHERE id = %s
            """, (program_id,))
            
            conn.commit()
            return True

def get_all_transactions():
    """Get all payment transactions with optional program details"""
    with pool.connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT p.id, p.program_id, p.reference, p.amount, p.status, p.created_at, prog.name, p.payment_type
                FROM payments p
                LEFT JOIN programs prog ON p.program_id = prog.id
                ORDER BY p.created_at DESC
            """)
            return [
                {
                    "id": r[0],
                    "program_id": r[1],
                    "reference": r[2],
                    "amount": r[3],
                    "status": r[4],
                    "created_at": r[5],
                    "program_name": r[6] if r[6] else "N/A",
                    "payment_type": r[7]
                }
                for r in cursor.fetchall()
            ]

def get_transaction_by_id(transaction_id):
    """Get a specific transaction by ID with extended details"""
    with pool.connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT p.id, p.program_id, p.reference, p.amount, p.status, p.created_at, prog.name, u.first_name, p.payment_type, p.metadata
                FROM payments p
                LEFT JOIN programs prog ON p.program_id = prog.id
                LEFT JOIN users u ON prog.created_by = u.id
                WHERE p.id = %s
            """, (transaction_id,))
            r = cursor.fetchone()
            if r:
                return {
                    "id": r[0],
                    "program_id": r[1],
                    "reference": r[2],
                    "amount": r[3],
                    "status": r[4],
                    "created_at": r[5],
                    "program_name": r[6] if r[6] else "N/A",
                    "user_name": r[7] if r[7] else "N/A",
                    "payment_type": r[8],
                    "metadata": r[9]
                }
            return None

def get_all_users():
    """Get all telegram users (deduplicated by telegram_id)"""
    with pool.connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT MIN(id) AS id, telegram_id, MAX(username) AS username, MAX(first_name) AS first_name
                FROM users
                GROUP BY telegram_id
                ORDER BY id DESC
            """)
            return [
                {
                    "id": r[0],
                    "telegram_id": r[1],
                    "username": r[2],
                    "first_name": r[3]
                }
                for r in cursor.fetchall()
            ]

# -------------------------
# RESOURCE TYPE SPECIFIC DUPLICATE CHECKING
# -------------------------
# Resource types with duplicate checking:
# 1. Notes (check duplicates) - documents: pdf, docx, ppt
# 2. PQ Images (NO duplicate check) - files: gif, jpeg, jpg, png
# 3. PQ Files (NO duplicate check) - documents: pdf, docx
# 4. Textbooks (check duplicates) - documents: pdf, docx
# 5. Extra Study Files (NO duplicate check) - documents: docx, pdf
# 6. Code (NO duplicate check) - documents: py, cpp, zip, java, js
# 7. Drawings (NO duplicate check) - files: io, pdf, png
# 8. Video Files (check duplicates) - documents: mp4, avi, mkv, mov

DUPLICATE_CHECK_RESOURCES = {
    "notes": True,  # Resource Type ID 1
    "textbooks": True,  # Resource Type ID 4
    "video": True  # Resource Type ID 8 (if exists)
}

def get_resource_type_by_name(resource_type_name):
    """Get resource type ID by name"""
    with pool.connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT id FROM resource_types
                WHERE LOWER(name) = LOWER(%s)
            """, (resource_type_name,))
            r = cursor.fetchone()
            return r[0] if r else None

def should_check_duplicate(resource_type_id):
    """Determine if a resource type requires duplicate checking"""
    with pool.connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT name FROM resource_types WHERE id = %s
            """, (resource_type_id,))
            r = cursor.fetchone()
            if r:
                type_name = r[0].lower()
                # Check if this resource type requires duplicate checking
                return type_name in ['notes', 'textbooks', 'video files', 'videos']
            return False

def check_duplicate_resource_by_type(course_id, resource_type_id, file_name):
    """Check for duplicate resources based on resource type"""
    should_check = should_check_duplicate(resource_type_id)
    
    if not should_check:
        # No duplicate check needed for this resource type
        return False
    
    # Perform duplicate check
    with pool.connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT 1
                FROM resources r
                JOIN courses c ON r.course_id = c.id
                WHERE r.course_id = %s 
                  AND r.resource_type_id = %s 
                  AND LOWER(r.file_name) = LOWER(%s)
            """, (course_id, resource_type_id, file_name))
            return cursor.fetchone() is not None

def save_resource_with_type_check(course_id, resource_type_id, file_id, file_name, uploader_id):
    """Save resource with proper duplicate checking based on type"""
    # Check if duplicate checking is needed for this resource type
    if check_duplicate_resource_by_type(course_id, resource_type_id, file_name):
        return None  # Duplicate found
    
    # Save resource
    with pool.connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO resources (course_id, resource_type_id, file_id, file_name, uploader_id)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (file_id) DO NOTHING
                RETURNING id
            """, (course_id, resource_type_id, file_id, file_name, uploader_id))
            conn.commit()
            result = cursor.fetchone()
            return result[0] if result else None

# -------------------------
# Admin Messages Management
# -------------------------
def save_admin_message(telegram_id, username, first_name, message_text, message_type='general'):
    """Save a message sent to admin by a user"""
    with pool.connection() as conn:
        with conn.cursor() as cursor:
            # Get or create user
            cursor.execute("""
                SELECT id FROM users WHERE telegram_id = %s
            """, (telegram_id,))
            user_row = cursor.fetchone()
            user_id = user_row[0] if user_row else None
            
            # Save admin message
            cursor.execute("""
                INSERT INTO admin_messages (user_id, telegram_id, username, first_name, message_text, message_type)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (user_id, telegram_id, username, first_name, message_text, message_type))
            conn.commit()
            return cursor.fetchone()[0]

def get_all_admin_messages(limit=100):
    """Get all messages sent to admin, newest first"""
    with pool.connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT id, telegram_id, username, first_name, message_text, message_type, 
                       handled, handled_by, created_at
                FROM admin_messages
                ORDER BY created_at DESC
                LIMIT %s
            """, (limit,))
            
            results = cursor.fetchall()
            messages = []
            for row in results:
                messages.append({
                    'id': row[0],
                    'telegram_id': row[1],
                    'username': row[2],
                    'first_name': row[3],
                    'message_text': row[4],
                    'message_type': row[5],
                    'handled': row[6],
                    'handled_by': row[7],
                    'created_at': row[8]
                })
            return messages

def get_unhandled_admin_messages():
    """Get messages that haven't been responded to yet"""
    with pool.connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT id, telegram_id, username, first_name, message_text, message_type, created_at
                FROM admin_messages
                WHERE handled = FALSE
                ORDER BY created_at ASC
            """)
            
            results = cursor.fetchall()
            messages = []
            for row in results:
                messages.append({
                    'id': row[0],
                    'telegram_id': row[1],
                    'username': row[2],
                    'first_name': row[3],
                    'message_text': row[4],
                    'message_type': row[5],
                    'created_at': row[6]
                })
            return messages

def mark_message_handled(message_id, handled_by_username):
    """Mark an admin message as handled"""
    with pool.connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                UPDATE admin_messages
                SET handled = TRUE, handled_by = %s, handled_at = NOW()
                WHERE id = %s
            """, (handled_by_username, message_id))
            conn.commit()

def get_admin_messages_count():
    """Get count of unhandled admin messages"""
    with pool.connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM admin_messages WHERE handled = FALSE")
            return cursor.fetchone()[0]

def count_active_programs():
    """Count the number of programs with is_active = TRUE"""
    with pool.connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM programs WHERE is_active = TRUE")
            return cursor.fetchone()[0]

def promote_program(program_id):
    """Bumps up the active level sequence of a program by 100 dynamically"""
    with pool.connection() as conn:
        with conn.cursor() as cursor:
            try:
                cursor.execute("""
                    UPDATE programs
                    SET level = (CAST(NULLIF(REGEXP_REPLACE(level, '\D', '', 'g'), '') AS INTEGER) + 100)::text || ' Level'
                    WHERE id = %s
                    RETURNING level
                """, (program_id,))
                conn.commit()
                res = cursor.fetchone()
                return res[0] if res else None
            except Exception as e:
                print(f"ERROR: promote_program failed - {str(e)}")
                return None

def check_archive_access(user_id, target_level=None, target_course_id=None):
    """Validates multi-tiered access matrix"""
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

def get_past_levels(program_id, current_level_str):
    """Returns a list of levels less than the current active level"""
    try:
        current_level_int = int(''.join(filter(str.isdigit, current_level_str)))
        with pool.connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT DISTINCT academic_level
                    FROM courses
                    WHERE program_id = %s 
                      AND CAST(NULLIF(REGEXP_REPLACE(academic_level, '\D', '', 'g'), '') AS INTEGER) < %s
                    ORDER BY CAST(NULLIF(REGEXP_REPLACE(academic_level, '\D', '', 'g'), '') AS INTEGER) DESC
                """, (program_id, current_level_int))
                return [r[0] for r in cursor.fetchall()]
    except Exception as e:
        print(f"ERROR: get_past_levels failed - {str(e)}")
        return []

def get_courses_by_level_and_semester(program_id, level, semester):
    """Fetch courses for a specific historical level and semester"""
    with pool.connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT id, course_code
                FROM courses
                WHERE program_id = %s AND academic_level = %s AND semester = %s
                ORDER BY course_code
            """, (program_id, level, semester))
            return [{"id": r[0], "course_code": r[1]} for r in cursor.fetchall()]
