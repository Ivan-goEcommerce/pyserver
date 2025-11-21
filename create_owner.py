#!/usr/bin/env python3
"""
Create n8n owner account by directly inserting into the Postgres database.
This script waits for the database and n8n service to be ready, then creates
the owner account using SQL INSERT statement.
"""

import os
import sys
import time
import psycopg2
from password_utils import generate_secure_password, hash_password
from otn_notification import send_otn_notification
from agentic_webhook import send_agentic_webhook


def wait_for_postgres(host, port, database, user, password, max_retries=30, retry_interval=2):
    """
    Wait for PostgreSQL database to be ready.
    
    Args:
        host (str): Database host
        port (int): Database port
        database (str): Database name
        user (str): Database user
        password (str): Database password
        max_retries (int): Maximum number of retry attempts
        retry_interval (int): Seconds to wait between retries
    
    Returns:
        bool: True if database is ready, False otherwise
    """
    print(f"Waiting for PostgreSQL database at {host}:{port}...")
    
    for attempt in range(max_retries):
        try:
            conn = psycopg2.connect(
                host=host,
                port=port,
                database=database,
                user=user,
                password=password,
                connect_timeout=5
            )
            conn.close()
            print("PostgreSQL database is ready!")
            return True
        except psycopg2.OperationalError as e:
            if attempt < max_retries - 1:
                print(f"Database not ready yet (attempt {attempt + 1}/{max_retries}): {e}")
                time.sleep(retry_interval)
            else:
                print(f"Failed to connect to database after {max_retries} attempts: {e}")
                return False
    
    return False


def check_user_exists(conn, email):
    """
    Check if a user with the given email already exists.
    
    Args:
        conn: PostgreSQL connection object
        email (str): Email address to check
    
    Returns:
        bool: True if user exists, False otherwise
    """
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM public.user WHERE email = %s",
                (email,)
            )
            count = cur.fetchone()[0]
            return count > 0
    except Exception as e:
        print(f"Error checking if user exists: {e}")
        return False


def get_table_columns(conn, table_name='user', schema='public'):
    """
    Get list of columns in the user table.
    
    Args:
        conn: PostgreSQL connection object
        table_name (str): Table name
        schema (str): Schema name
    
    Returns:
        list: List of column names
    """
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_schema = %s AND table_name = %s
                ORDER BY ordinal_position
            """, (schema, table_name))
            columns = [row[0] for row in cur.fetchall()]
            return columns
    except Exception as e:
        print(f"Error getting table columns: {e}")
        return []


def create_owner_account(host, port, database, user, password, 
                        owner_email, owner_first_name, owner_last_name,
                        owner_password=None):
    """
    Create n8n owner account by inserting directly into the database.
    
    Args:
        host (str): Database host
        port (int): Database port
        database (str): Database name
        user (str): Database user
        password (str): Database password
        owner_email (str): Owner email address
        owner_first_name (str): Owner first name
        owner_last_name (str): Owner last name
        owner_password (str, optional): Plain text password. If None, generates a secure password.
    
    Returns:
        tuple: (success: bool, password: str) - Success status and the password used
    """
    # Generate password if not provided
    if owner_password is None:
        owner_password = generate_secure_password()
    
    # Hash the password using bcrypt (n8n uses bcrypt with 10 rounds)
    hashed_password = hash_password(owner_password)
    
    try:
        # Connect to database
        print(f"Connecting to PostgreSQL database at {host}:{port}...")
        conn = psycopg2.connect(
            host=host,
            port=port,
            database=database,
            user=user,
            password=password
        )
        
        # Check if user already exists
        if check_user_exists(conn, owner_email):
            print(f"User with email {owner_email} already exists. Skipping creation.")
            conn.close()
            return True, None
        
        # Get table columns to understand the schema
        print("Inspecting user table schema...")
        columns = get_table_columns(conn, 'user', 'public')
        print(f"Found columns: {', '.join(columns)}")
        
        # Insert the owner account
        print(f"Creating owner account for {owner_email}...")
        with conn.cursor() as cur:
            # Determine the correct role column name
            role_column = None
            if 'roleSlug' in columns:
                role_column = 'roleSlug'
            elif 'role' in columns:
                role_column = 'role'
            else:
                print("WARNING: No role column found. Trying with roleSlug anyway...")
                role_column = 'roleSlug'
            
            # Build INSERT statement with proper column names
            # Use minimal required columns to avoid issues with defaults
            insert_query = f"""
                INSERT INTO public.user (email, password, "firstName", "lastName", "{role_column}")
                VALUES (%s, %s, %s, %s, 'owner')
            """
            
            print(f"Executing: INSERT INTO public.user (email, password, firstName, lastName, {role_column})")
            cur.execute(
                insert_query,
                (owner_email, hashed_password, owner_first_name, owner_last_name)
            )
            
            conn.commit()
            print(f"Successfully created owner account for {owner_email}")
        
        conn.close()
        return True, owner_password
        
    except psycopg2.Error as e:
        print(f"Database error while creating owner account: {e}")
        import traceback
        traceback.print_exc()
        return False, None
    except Exception as e:
        print(f"Unexpected error while creating owner account: {e}")
        import traceback
        traceback.print_exc()
        return False, None


def main():
    """Main function to create n8n owner account."""
    # Get configuration from environment variables
    db_host = os.getenv('DB_POSTGRESDB_HOST', 'postgres')
    db_port = int(os.getenv('DB_POSTGRESDB_PORT', '5432'))
    db_database = os.getenv('DB_POSTGRESDB_DATABASE', 'n8n')
    db_user = os.getenv('DB_POSTGRESDB_USER', 'n8n')
    db_password = os.getenv('DB_POSTGRESDB_PASSWORD', 'n8n')
    
    owner_email = os.getenv('N8N_DEFAULT_EMAIL', 'Ivan.Levshyn@go-ecommerce.de')
    owner_first_name = os.getenv('N8N_DEFAULT_FIRST_NAME', 'Ivan')
    owner_last_name = os.getenv('N8N_DEFAULT_LAST_NAME', 'Levshyn')
    n8n_instance_url = os.getenv('N8N_INSTANCE_URL', 'http://n8n-ivan.go-ecommerce.de/')
    
    print("=" * 60)
    print("n8n Owner Account Creation Script")
    print("=" * 60)
    print(f"Database: {db_host}:{db_port}/{db_database}")
    print(f"Owner: {owner_first_name} {owner_last_name} ({owner_email})")
    print("=" * 60)
    
    # Wait for PostgreSQL to be ready
    if not wait_for_postgres(db_host, db_port, db_database, db_user, db_password):
        print("ERROR: Could not connect to PostgreSQL database")
        sys.exit(1)
    
    # Wait a bit more for n8n to initialize the database schema
    print("Waiting for n8n to initialize database schema...")
    time.sleep(10)
    
    # Create the owner account
    success, password = create_owner_account(
        db_host, db_port, db_database, db_user, db_password,
        owner_email, owner_first_name, owner_last_name
    )
    
    if not success:
        print("ERROR: Failed to create owner account")
        sys.exit(1)
    
    if password:
        print(f"\nOwner account created successfully!")
        print(f"Email: {owner_email}")
        print(f"Password: {password}")
        
        # Send notification via OTN
        credential_url = send_otn_notification(owner_email, password)
        
        # Send credentials to agentic webhook
        access_key = os.getenv('AGENTIC_ACCESS_KEY')
        application = os.getenv('AGENTIC_APPLICATION')
        
        if credential_url:
            send_agentic_webhook(
                owner_first_name,
                owner_last_name,
                owner_email,
                n8n_instance_url,
                credential_url,
                access_key,
                application
            )
    else:
        print("\nOwner account already exists or password was not generated.")
    
    print("\nScript completed successfully!")


if __name__ == "__main__":
    main()

