#!/usr/bin/env python3
"""Quick test to verify database connection and payments table"""

import psycopg2
from dotenv import load_dotenv
import os

load_dotenv()

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "database": os.getenv("DB_DATABASE"),
    "port": int(os.getenv("DB_PORT", 5432)),
}

print(f"Attempting to connect with config: {DB_CONFIG}")

try:
    conn = psycopg2.connect(**DB_CONFIG)
    print("✅ Database connection successful!")
    
    with conn.cursor() as cursor:
        # Check if payments table exists
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'payments'
            );
        """)
        table_exists = cursor.fetchone()[0]
        print(f"✅ Payments table exists: {table_exists}")
        
        if table_exists:
            # Check table structure
            cursor.execute("""
                SELECT column_name, data_type 
                FROM information_schema.columns 
                WHERE table_name = 'payments'
                ORDER BY ordinal_position;
            """)
            print("\n📋 Payments table structure:")
            for col_name, col_type in cursor.fetchall():
                print(f"   - {col_name}: {col_type}")
            
            # Check for any existing payments
            cursor.execute("SELECT COUNT(*) FROM payments;")
            count = cursor.fetchone()[0]
            print(f"\n📊 Total payments in database: {count}")
            
            if count > 0:
                cursor.execute("""
                    SELECT id, program_id, reference, amount, status, created_at 
                    FROM payments 
                    ORDER BY created_at DESC 
                    LIMIT 10;
                """)
                print("\n📝 Recent payments:")
                print(f"{'ID':<5} {'Program':<10} {'Reference':<50} {'Amount':<10} {'Status':<10} {'Created':<25}")
                print("-" * 110)
                for id, prog_id, ref, amount, status, created_at in cursor.fetchall():
                    print(f"{id:<5} {prog_id:<10} {ref:<50} {amount:<10} {status:<10} {str(created_at):<25}")
    
    conn.close()
    print("\n✅ All checks passed!")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
