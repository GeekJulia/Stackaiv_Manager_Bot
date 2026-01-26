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

# Create a cursor
cursor = conn.cursor()

# -------------------------
# Save or Update Telegram User
# -------------------------
def save_user(telegram_id, username, first_name):
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
def save_program(level, college, program_name, telegram_id):
    query = """
    INSERT INTO programs (level, college, name, created_by)
    VALUES (%s, %s, %s, %s)
    RETURNING id;
    """
    cursor.execute(query, (level, college, program_name, telegram_id))
    conn.commit()
    return cursor.fetchone()[0]