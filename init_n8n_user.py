#!/usr/bin/env python3
"""
Script to create an n8n owner account directly in PostgreSQL database.
This bypasses the n8n setup wizard.
"""
import os
import sys
import time
import psycopg2
import bcrypt

# Database connection parameters
DB_HOST = os.getenv('DB_POSTGRESDB_HOST', 'postgres')
DB_PORT = os.getenv('DB_POSTGRESDB_PORT', '5432')
DB_NAME = os.getenv('DB_POSTGRESDB_DATABASE', 'n8n')
DB_USER = os.getenv('DB_POSTGRESDB_USER', 'n8n')
DB_PASSWORD = os.getenv('DB_POSTGRESDB_PASSWORD', 'n8n')

# Admin user credentials
ADMIN_EMAIL = os.getenv('N8N_ADMIN_EMAIL', 'admin@example.com')
ADMIN_PASSWORD = os.getenv('N8N_ADMIN_PASSWORD', 'admin123')
ADMIN_FIRST_NAME = os.getenv('N8N_ADMIN_FIRST_NAME', 'Admin')
ADMIN_LAST_NAME = os.getenv('N8N_ADMIN_LAST_NAME', 'User')

MAX_RETRIES = 30
RETRY_DELAY = 2


def wait_for_database():
    """Wait for PostgreSQL to be ready."""
    print("Waiting for PostgreSQL to be ready...")
    for i in range(MAX_RETRIES):
        try:
            conn = psycopg2.connect(
                host=DB_HOST,
                port=DB_PORT,
                database=DB_NAME,
                user=DB_USER,
                password=DB_PASSWORD
            )
            conn.close()
            print("PostgreSQL is ready!")
            return True
        except psycopg2.OperationalError as e:
            if i < MAX_RETRIES - 1:
                print(f"Waiting for database... (attempt {i+1}/{MAX_RETRIES})")
                time.sleep(RETRY_DELAY)
            else:
                print(f"Failed to connect to database: {e}")
                return False
    return False


def hash_password(password):
    """Hash password using bcrypt (same as n8n uses)."""
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')


def get_table_columns(cur, table_name):
    """Get list of columns in a table."""
    cur.execute("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = %s
        ORDER BY ordinal_position
    """, (table_name,))
    return [row[0] for row in cur.fetchall()]


def create_owner_account():
    """Ensure no users exist - login will be completely skipped."""
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
        cur = conn.cursor()

        # Check if user table exists
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'user'
            )
        """)
        if not cur.fetchone()[0]:
            print("User table does not exist yet. Login will be skipped automatically.")
            cur.close()
            conn.close()
            return True

        # Delete ALL users to ensure login is completely skipped
        print("Checking for existing users...")
        cur.execute("SELECT COUNT(*) FROM \"user\"")
        user_count = cur.fetchone()[0]
        
        if user_count > 0:
            print(f"Found {user_count} user(s). Deleting all users to skip login completely...")
            cur.execute("DELETE FROM \"user\"")
            conn.commit()
            print("All users deleted. Login will be completely skipped - direct access to n8n!")
        else:
            print("No users found. Login will be skipped automatically - direct access to n8n!")
        
        cur.close()
        conn.close()
        return True

    except psycopg2.Error as e:
        print(f"Database error: {e}")
        import traceback
        traceback.print_exc()
        return False
    except Exception as e:
        print(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main function."""
    print("=" * 50)
    print("n8n Owner Account Initialization Script")
    print("=" * 50)

    if not wait_for_database():
        sys.exit(1)

    # Wait for n8n to initialize the database schema and be ready
    print("Waiting for n8n to initialize database schema...")
    max_schema_wait = 120  # Wait up to 120 seconds for schema
    schema_wait_interval = 3
    
    schema_ready = False
    for i in range(max_schema_wait // schema_wait_interval):
        try:
            conn = psycopg2.connect(
                host=DB_HOST,
                port=DB_PORT,
                database=DB_NAME,
                user=DB_USER,
                password=DB_PASSWORD
            )
            cur = conn.cursor()
            # Check if user table exists
            cur.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'user'
                )
            """)
            table_exists = cur.fetchone()[0]
            
            if table_exists:
                print("Database schema is ready!")
                schema_ready = True
                cur.close()
                conn.close()
                break
            
            cur.close()
            conn.close()
        except Exception as e:
            print(f"Error checking schema: {e}")
        
        if not schema_ready and i < (max_schema_wait // schema_wait_interval) - 1:
            print(f"Schema not ready yet, waiting... ({i+1} attempts)")
            time.sleep(schema_wait_interval)
    
    if not schema_ready:
        print("WARNING: Schema might not be fully ready, but attempting to create user anyway...")

    if create_owner_account():
        print("=" * 50)
        print("Initialization completed successfully!")
        print("=" * 50)
        sys.exit(0)
    else:
        print("=" * 50)
        print("Initialization failed!")
        print("=" * 50)
        sys.exit(1)


if __name__ == "__main__":
    main()

