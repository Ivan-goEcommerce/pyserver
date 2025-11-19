#!/usr/bin/env python3
"""
Script to automatically create a user and session in n8n database for automatic login.
This ensures that when accessing the URL, the user is immediately logged in to the workspace.
"""
import os
import sys
import time
import uuid
import bcrypt
import psycopg2
import requests

# Database connection parameters
DB_HOST = os.getenv('DB_POSTGRESDB_HOST', 'postgres')
DB_PORT = os.getenv('DB_POSTGRESDB_PORT', '5432')
DB_NAME = os.getenv('DB_POSTGRESDB_DATABASE', 'n8n')
DB_USER = os.getenv('DB_POSTGRESDB_USER', 'n8n')
DB_PASSWORD = os.getenv('DB_POSTGRESDB_PASSWORD', 'n8n')

# Default user credentials
DEFAULT_USER_EMAIL = os.getenv('N8N_DEFAULT_EMAIL', 'admin@n8n.local')
DEFAULT_USER_PASSWORD = os.getenv('N8N_DEFAULT_PASSWORD', 'admin')
DEFAULT_USER_FIRST_NAME = os.getenv('N8N_DEFAULT_FIRST_NAME', 'Admin')
DEFAULT_USER_LAST_NAME = os.getenv('N8N_DEFAULT_LAST_NAME', 'User')

# n8n API endpoint
N8N_HOST = os.getenv('N8N_HOST', 'n8n')
N8N_PORT = os.getenv('N8N_PORT', '5678')
N8N_PROTOCOL = os.getenv('N8N_PROTOCOL', 'http')
N8N_BASE_URL = f"{N8N_PROTOCOL}://{N8N_HOST}:{N8N_PORT}"

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
    """Hash password using bcrypt (n8n's default)."""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')


def create_or_get_user():
    """Create default user if it doesn't exist, or get existing user.
    
    Uses direct SQL INSERT to create owner account as described in the approach.
    Handles different n8n schema versions automatically.
    """
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
            print("User table does not exist yet. Waiting for n8n to initialize...")
            cur.close()
            conn.close()
            return None

        # Check if user already exists
        cur.execute('SELECT id, email FROM "user" WHERE email = %s', (DEFAULT_USER_EMAIL,))
        existing_user = cur.fetchone()
        
        if existing_user:
            user_id = existing_user[0]
            print(f"User '{DEFAULT_USER_EMAIL}' already exists (ID: {user_id})")
            cur.close()
            conn.close()
            return user_id
        
        # Create new user with hashed password
        print(f"Creating owner user '{DEFAULT_USER_EMAIL}'...")
        user_id = str(uuid.uuid4())
        password_hash = hash_password(DEFAULT_USER_PASSWORD)
        
        # Get current timestamp
        cur.execute("SELECT NOW()")
        now = cur.fetchone()[0]
        
        # Get available columns in user table
        cur.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_schema = 'public' AND table_name = 'user' 
            ORDER BY ordinal_position
        """)
        columns = [row[0] for row in cur.fetchall()]
        print(f"Available columns in user table: {columns}")
        
        # Build INSERT statement - try simpler approach first, then fallback
        insert_cols = []
        insert_vals = []
        placeholders = []
        
        # Required columns
        if 'id' in columns:
            insert_cols.append('id')
            insert_vals.append(user_id)
            placeholders.append('%s')
        
        if 'email' in columns:
            insert_cols.append('email')
            insert_vals.append(DEFAULT_USER_EMAIL)
            placeholders.append('%s')
        
        if 'password' in columns:
            insert_cols.append('password')
            insert_vals.append(password_hash)
            placeholders.append('%s')
        
        # Name columns
        first_name_col = None
        for col in ['firstName', 'firstname', 'first_name']:
            if col in columns:
                first_name_col = col
                break
        
        if first_name_col:
            if first_name_col == 'firstName':
                insert_cols.append('"firstName"')
            else:
                insert_cols.append(first_name_col)
            insert_vals.append(DEFAULT_USER_FIRST_NAME)
            placeholders.append('%s')
        
        last_name_col = None
        for col in ['lastName', 'lastname', 'last_name']:
            if col in columns:
                last_name_col = col
                break
        
        if last_name_col:
            if last_name_col == 'lastName':
                insert_cols.append('"lastName"')
            else:
                insert_cols.append(last_name_col)
            insert_vals.append(DEFAULT_USER_LAST_NAME)
            placeholders.append('%s')
        
        # Role assignment - try different approaches
        # Approach 1: Direct 'role' column with 'global:owner' value (older n8n versions)
        if 'role' in columns:
            insert_cols.append('role')
            insert_vals.append('global:owner')
            placeholders.append('%s')
            print("Using direct 'role' column with 'global:owner' value")
        # Approach 2: globalRoleId with subquery to role table (newer n8n versions)
        elif 'globalRoleId' in columns:
            insert_cols.append('"globalRoleId"')
            # Get owner role ID from role table
            cur.execute('SELECT id FROM "role" WHERE name = %s LIMIT 1', ('owner',))
            role_result = cur.fetchone()
            if role_result:
                insert_vals.append(role_result[0])
                placeholders.append('%s')
                print(f"Using globalRoleId with owner role ID: {role_result[0]}")
            else:
                print("WARNING: Owner role not found in role table, but continuing...")
        elif 'global_role_id' in columns:
            insert_cols.append('global_role_id')
            cur.execute('SELECT id FROM role WHERE name = %s LIMIT 1', ('owner',))
            role_result = cur.fetchone()
            if role_result:
                insert_vals.append(role_result[0])
                placeholders.append('%s')
                print(f"Using global_role_id with owner role ID: {role_result[0]}")
            else:
                print("WARNING: Owner role not found in role table, but continuing...")
        else:
            print("WARNING: No role column found, user may not have proper permissions")
        
        # Timestamps
        created_at_col = None
        for col in ['createdAt', 'created_at']:
            if col in columns:
                created_at_col = col
                break
        
        if created_at_col:
            if created_at_col == 'createdAt':
                insert_cols.append('"createdAt"')
            else:
                insert_cols.append(created_at_col)
            insert_vals.append(now)
            placeholders.append('%s')
        
        updated_at_col = None
        for col in ['updatedAt', 'updated_at']:
            if col in columns:
                updated_at_col = col
                break
        
        if updated_at_col:
            if updated_at_col == 'updatedAt':
                insert_cols.append('"updatedAt"')
            else:
                insert_cols.append(updated_at_col)
            insert_vals.append(now)
            placeholders.append('%s')
        
        # Build and execute the INSERT query
        insert_query = f"""
            INSERT INTO "user" (
                {', '.join(insert_cols)}
            ) VALUES (
                {', '.join(placeholders)}
            )
        """
        
        print(f"Executing INSERT with columns: {insert_cols}")
        cur.execute(insert_query, insert_vals)
        conn.commit()
        
        print(f"✓ Successfully created owner user '{DEFAULT_USER_EMAIL}' (ID: {user_id})")
        print(f"  Email: {DEFAULT_USER_EMAIL}")
        print(f"  Password: {DEFAULT_USER_PASSWORD}")
        print(f"  Role: global:owner")
        
        cur.close()
        conn.close()
        return user_id

    except psycopg2.Error as e:
        print(f"Database error: {e}")
        import traceback
        traceback.print_exc()
        return None
    except Exception as e:
        print(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return None


def wait_for_n8n_api():
    """Wait for n8n API to be ready."""
    print("Waiting for n8n API to be ready...")
    max_wait = 120
    wait_interval = 3
    
    for i in range(max_wait // wait_interval):
        try:
            response = requests.get(f"{N8N_BASE_URL}/healthz", timeout=5)
            if response.status_code == 200:
                print("n8n API is ready!")
                return True
        except Exception:
            pass
        
        if i < (max_wait // wait_interval) - 1:
            print(f"Waiting for n8n API... (attempt {i+1})")
            time.sleep(wait_interval)
    
    print("WARNING: n8n API might not be ready, but continuing...")
    return False


def login_via_api():
    """Login via n8n API to create a proper session and get session cookie."""
    try:
        print(f"Attempting to login via n8n API at {N8N_BASE_URL}...")
        
        # Login endpoint
        login_url = f"{N8N_BASE_URL}/rest/login"
        
        payload = {
            "email": DEFAULT_USER_EMAIL,
            "password": DEFAULT_USER_PASSWORD
        }
        
        # Use a session to maintain cookies
        session = requests.Session()
        response = session.post(login_url, json=payload, timeout=10)
        
        if response.status_code == 200:
            print("✓ Successfully logged in via API - session created!")
            # Get session cookie
            cookies = session.cookies.get_dict()
            if cookies:
                print(f"✓ Session cookie obtained: {list(cookies.keys())[0]}")
                # Save cookie to file for potential use by reverse proxy
                cookie_file = "/tmp/n8n_session_cookie.txt"
                try:
                    with open(cookie_file, 'w') as f:
                        for name, value in cookies.items():
                            f.write(f"{name}={value}\n")
                    print(f"✓ Session cookie saved to {cookie_file}")
                except Exception:
                    pass  # Ignore if we can't write to file
            return True
        elif response.status_code == 401:
            print(f"⚠ Login failed - incorrect credentials or user setup issue")
            return False
        else:
            print(f"Note: API login returned status {response.status_code}")
            return True
            
    except requests.exceptions.ConnectionError:
        print(f"Note: Could not connect to n8n API (n8n might still be starting)")
        return True
    except Exception as e:
        print(f"Note: API login skipped: {e}")
        return True


def wait_for_role_table():
    """Wait for role table to exist (needed for user creation)."""
    print("Waiting for role table to be available...")
    max_wait = 60
    wait_interval = 2
    
    for i in range(max_wait // wait_interval):
        try:
            conn = psycopg2.connect(
                host=DB_HOST,
                port=DB_PORT,
                database=DB_NAME,
                user=DB_USER,
                password=DB_PASSWORD
            )
            cur = conn.cursor()
            cur.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'role'
                )
            """)
            if cur.fetchone()[0]:
                cur.close()
                conn.close()
                return True
            cur.close()
            conn.close()
        except Exception:
            pass
        
        if i < (max_wait // wait_interval) - 1:
            time.sleep(wait_interval)
    
    return False


def main():
    """Main function."""
    print("=" * 50)
    print("n8n Auto-Login Setup Script")
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

    # Wait for role table
    if not wait_for_role_table():
        print("WARNING: Role table not found, but continuing...")

    # Create or get user
    user_id = create_or_get_user()
    
    if not user_id:
        print("=" * 50)
        print("Failed to create/get user!")
        print("=" * 50)
        sys.exit(1)
    
    # Wait for n8n API and login to create session
    wait_for_n8n_api()
    login_via_api()
    
    print("=" * 50)
    print("Initialization completed successfully!")
    print(f"User: {DEFAULT_USER_EMAIL}")
    print(f"Password: {DEFAULT_USER_PASSWORD}")
    print("")
    print("NOTE: For automatic login without login screen:")
    print("- The user has been created in the database")
    print("- When accessing n8n URL, you may need to login once")
    print("- After first login, the session will persist")
    print("- For true auto-login, consider using browser automation or")
    print("  reverse proxy cookie injection")
    print("=" * 50)
    sys.exit(0)


if __name__ == "__main__":
    main()

