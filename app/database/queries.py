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
