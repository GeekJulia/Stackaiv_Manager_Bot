import os
import psycopg # type: ignore
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Create connection
conn = psycopg.connect(
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
    """Get program ID for a user, returns None if user has no program"""
    with conn.cursor() as cursor:
        cursor.execute("""
            SELECT p.id
            FROM programs p
            JOIN users u ON p.created_by = u.id
            WHERE u.telegram_id = %s
        """, (telegram_id,))
        result = cursor.fetchone()
        return result[0] if result else None

def user_has_program(telegram_id):
    """Check if a user already has a registered program"""
    return get_user_program_id(telegram_id) is not None

def get_user_program_info(telegram_id):
    """Get full program information for a user"""
    program_id = get_user_program_id(telegram_id)
    if program_id:
        return get_program_info(program_id, include_user_id=False)
    return None


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

def get_program_info(program_id, include_user_id=False):
    """Get program information by program ID
    
    Args:
        program_id: The program ID to fetch
        include_user_id: If True, includes user_id (created_by) in the result
    
    Returns:
        Dictionary with program info: id, level, college, program_name, and optionally user_id
    """
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

# -------------------------
# PAYMENT & ACTIVATION FUNCTIONS
# -------------------------

def save_payment(program_id, reference, amount, status):
    """Save payment transaction record"""
    try:
        with conn.cursor() as cursor:
            query = """
            INSERT INTO payments (program_id, reference, amount, status)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (reference) DO UPDATE
            SET status = EXCLUDED.status
            RETURNING id;
            """
            cursor.execute(query, (program_id, reference, amount, status))
            conn.commit()
            result = cursor.fetchone()[0]
            print(f"DEBUG: Payment saved - reference={reference}, program_id={program_id}, amount={amount}, status={status}")
            return result
    except Exception as e:
        print(f"ERROR: save_payment failed - {str(e)}")
        raise

def get_payment_by_reference(reference):
    """Get payment record by Paystack reference"""
    try:
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
    """Get all payment transactions"""
    with conn.cursor() as cursor:
        cursor.execute("""
            SELECT p.id, p.program_id, p.reference, p.amount, p.status, p.created_at, prog.name
            FROM payments p
            JOIN programs prog ON p.program_id = prog.id
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
                "program_name": r[6]
            }
            for r in cursor.fetchall()
        ]

def get_transaction_by_id(transaction_id):
    """Get a specific transaction by ID"""
    with conn.cursor() as cursor:
        cursor.execute("""
            SELECT p.id, p.program_id, p.reference, p.amount, p.status, p.created_at, prog.name, u.first_name
            FROM payments p
            JOIN programs prog ON p.program_id = prog.id
            JOIN users u ON prog.created_by = u.id
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
                "program_name": r[6],
                "user_name": r[7]
            }
        return None

def get_all_users():
    """Get all telegram users (deduplicated by telegram_id)"""
    with conn.cursor() as cursor:
        # DISTINCT ON ensures one row per telegram_id (latest by created_at)
        cursor.execute("""
            SELECT DISTINCT ON (telegram_id) id, telegram_id, username, first_name
            FROM users
            ORDER BY telegram_id, created_at DESC
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
    with conn.cursor() as cursor:
        cursor.execute("""
            SELECT id FROM resource_types
            WHERE LOWER(name) = LOWER(%s)
        """, (resource_type_name,))
        r = cursor.fetchone()
        return r[0] if r else None

def should_check_duplicate(resource_type_id):
    """Determine if a resource type requires duplicate checking"""
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
    with conn.cursor() as cursor:
        cursor.execute("""
            SELECT COUNT(*)
            FROM resources
            WHERE course_id = %s 
            AND resource_type_id = %s 
            AND LOWER(file_name) = LOWER(%s)
        """, (course_id, resource_type_id, file_name))
        count = cursor.fetchone()[0]
        return count > 0

def save_resource_with_type_check(course_id, resource_type_id, file_id, file_name, uploader_id):
    """Save resource with proper duplicate checking based on type"""
    # Check if duplicate checking is needed for this resource type
    if check_duplicate_resource_by_type(course_id, resource_type_id, file_name):
        return None  # Duplicate found
    
    # Save resource
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
    with conn.cursor() as cursor:
        cursor.execute("""
            UPDATE admin_messages
            SET handled = TRUE, handled_by = %s, handled_at = NOW()
            WHERE id = %s
        """, (handled_by_username, message_id))
        conn.commit()

def get_admin_messages_count():
    """Get count of unhandled admin messages"""
    with conn.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM admin_messages WHERE handled = FALSE")
        return cursor.fetchone()[0]

def count_active_programs():
    """Count the number of programs with is_active = TRUE"""
    with conn.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM programs WHERE is_active = TRUE")
        return cursor.fetchone()[0]