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
