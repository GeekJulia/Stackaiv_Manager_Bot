import os
import psycopg2
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Create connection
conn = psycopg2.connect(
    host=os.getenv("DB_HOST"),
    user=os.getenv("DB_USER"),
    port=os.getenv("DB_PORT"),
    password=os.getenv("DB_PASSWORD"),
    dbname=os.getenv("DB_DATABASE")
)

# -------------------------
# Save or Update Telegram User
# -------------------------
def save_user(telegram_id, username, first_name):
    with conn.cursor() as cursor:
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

# -------------------------
# Save Program Registration
# -------------------------
def save_program(level, college, program_name, user_id):
    with conn.cursor() as cursor:
        query = """
        INSERT INTO programs (level, college, name, created_by)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (created_by) DO UPDATE
        SET level = EXCLUDED.level,
            college = EXCLUDED.college,
            name = EXCLUDED.name
        RETURNING id;
        """
        cursor.execute(query, (level, college, program_name, user_id))
        conn.commit()
        return cursor.fetchone()[0]
    
def get_user_program_id(telegram_id):
    with conn.cursor() as cursor:
        cursor.execute("""
            SELECT p.id
            FROM programs p
            JOIN users u ON p.created_by = u.id
            WHERE u.telegram_id = %s
        """, (telegram_id,))
        return cursor.fetchone()[0]


def save_courses(program_id, course_codes):
    ids = []
    with conn.cursor() as cursor:
        for code in course_codes:
            cursor.execute("""
                INSERT INTO courses (program_id, course_code)
                VALUES (%s, %s)
                RETURNING id
            """, (program_id, code))
            ids.append(cursor.fetchone()[0])
        conn.commit()
    return ids


def get_resource_types():
    with conn.cursor() as cursor:
        cursor.execute("SELECT id, name FROM resource_types")
        return [{"id": r[0], "name": r[1]} for r in cursor.fetchall()]


def save_course_resource_types(course_id, resource_type_ids):
    with conn.cursor() as cursor:
        for r_id in resource_type_ids:
            cursor.execute("""
                INSERT INTO course_resource_types (course_id, resource_type_id)
                VALUES (%s, %s)
                ON CONFLICT DO NOTHING
            """, (course_id, r_id))
        conn.commit()

def get_courses_by_program(program_id):
    with conn.cursor() as cursor:
        cursor.execute("""
            SELECT id, course_code
            FROM courses
            WHERE program_id = %s
        """, (program_id,))
        return [{"id": r[0], "course_code": r[1]} for r in cursor.fetchall()]


def save_resource(course_id, resource_type_id, file_id, file_name, uploader_id):
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
    with conn.cursor() as cursor:
        cursor.execute("""
            SELECT file_id, file_name
            FROM resources
            WHERE course_id = %s AND resource_type_id = %s
            ORDER BY created_at
        """, (course_id, resource_type_id))
        return [{"file_id": r[0], "file_name": r[1]} for r in cursor.fetchall()]
    
def get_course_info(course_id):
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

def check_program_exists(level, college, program_name):
    """Check if a program already exists in the database"""
    with conn.cursor() as cursor:
        cursor.execute("""
            SELECT id, level, college, name, created_by
            FROM programs
            WHERE level = %s AND college = %s AND name = %s
            LIMIT 1
        """, (level, college, program_name))
        r = cursor.fetchone()
        if r:
            return {
                "id": r[0],
                "level": r[1],
                "college": r[2],
                "program_name": r[3],
                "user_id": r[4]
            }
        return None

def get_program_creator(program_id):
    """Get the user who created a specific program"""
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

def get_program_info(program_id):
    """Get program information by program ID"""
    with conn.cursor() as cursor:
        cursor.execute("""
            SELECT id, level, college, name, created_by
            FROM programs
            WHERE id = %s
        """, (program_id,))
        r = cursor.fetchone()
        if r:
            return {
                "id": r[0],
                "level": r[1],
                "college": r[2],
                "program_name": r[3],
                "user_id": r[4]
            }
        return None

def clear_user_program_data(program_id):
    """Clear all courses and resource types associated with a program"""
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

# -------------------------
# GROUP MANAGEMENT FUNCTIONS
# -------------------------

def get_program_by_id(program_id):
    """Get program details by program ID"""
    with conn.cursor() as cursor:
        cursor.execute("""
            SELECT id, level, college, name
            FROM programs
            WHERE id = %s
        """, (program_id,))
        r = cursor.fetchone()
        if r:
            return {
                "id": r[0],
                "level": r[1],
                "college": r[2],
                "name": r[3]
            }
        return None

def save_group(telegram_chat_id, program_id):
    """Save or update group chat with program ID"""
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

def get_group_program_id(telegram_chat_id):
    """Get program ID for a group chat"""
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
    with conn.cursor() as cursor:
        cursor.execute("""
            INSERT INTO approvals (resource_id, approved_by)
            VALUES (%s, %s)
        """, (resource_id, approved_by_telegram_id))
        conn.commit()