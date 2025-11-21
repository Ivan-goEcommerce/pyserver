#!/usr/bin/env python3
"""
Script to create n8n owner account in PostgreSQL database.
Waits for n8n to initialize its database schema, then inserts the owner account.
"""

import os
import sys
import time
import psycopg2
from psycopg2 import sql

# Import utility modules
from password_utils import generate_secure_password, hash_password
from otn_notification import send_otn_notification
from agentic_webhook import send_agentic_webhook

# Database connection parameters
DB_HOST = os.getenv('DB_POSTGRESDB_HOST', 'postgres')
DB_PORT = int(os.getenv('DB_POSTGRESDB_PORT', 5432))
DB_NAME = os.getenv('DB_POSTGRESDB_DATABASE', 'n8n')
DB_USER = os.getenv('DB_POSTGRESDB_USER', 'n8n')
DB_PASSWORD = os.getenv('DB_POSTGRESDB_PASSWORD', 'n8n')

# Owner account details
OWNER_EMAIL = os.getenv('N8N_DEFAULT_EMAIL', 'admin@example.com')
OWNER_FIRST_NAME = os.getenv('N8N_DEFAULT_FIRST_NAME', 'Admin')
OWNER_LAST_NAME = os.getenv('N8N_DEFAULT_LAST_NAME', 'User')
N8N_INSTANCE_URL = os.getenv('N8N_INSTANCE_URL', 'http://n8n-ivan.go-ecommerce.de/')

MAX_RETRIES = 30
RETRY_DELAY = 2


def wait_for_database():
    """Wait for PostgreSQL database to be ready."""
    print("Waiting for PostgreSQL database to be ready...")
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
            print("Database is ready!")
            return True
        except psycopg2.OperationalError as e:
            if i < MAX_RETRIES - 1:
                print(f"Database not ready yet, retrying in {RETRY_DELAY} seconds... ({i+1}/{MAX_RETRIES})")
                time.sleep(RETRY_DELAY)
            else:
                print(f"Failed to connect to database: {e}")
                return False
    return False


def wait_for_n8n_schema():
    """Wait for n8n to create its database schema (user table)."""
    print("Waiting for n8n to initialize database schema...")
    for i in range(MAX_RETRIES):
        try:
            conn = psycopg2.connect(
                host=DB_HOST,
                port=DB_PORT,
                database=DB_NAME,
                user=DB_USER,
                password=DB_PASSWORD
            )
            cursor = conn.cursor()
            
            # Check if user table exists
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = 'user'
                );
            """)
            
            table_exists = cursor.fetchone()[0]
            cursor.close()
            conn.close()
            
            if table_exists:
                print("n8n schema is ready!")
                return True
            else:
                if i < MAX_RETRIES - 1:
                    print(f"Schema not ready yet, retrying in {RETRY_DELAY} seconds... ({i+1}/{MAX_RETRIES})")
                    time.sleep(RETRY_DELAY)
                else:
                    print("Timeout waiting for n8n schema to be created")
                    return False
        except psycopg2.Error as e:
            if i < MAX_RETRIES - 1:
                print(f"Error checking schema, retrying in {RETRY_DELAY} seconds... ({i+1}/{MAX_RETRIES})")
                time.sleep(RETRY_DELAY)
            else:
                print(f"Failed to check schema: {e}")
                return False
    return False


def get_user_table_columns(cursor):
    """Get all column names from the user table."""
    cursor.execute("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_schema = 'public' 
        AND table_name = 'user'
        ORDER BY ordinal_position;
    """)
    columns = [row[0] for row in cursor.fetchall()]
    return columns


def check_user_exists(cursor, email):
    """Check if user with given email already exists."""
    cursor.execute(
        sql.SQL("SELECT COUNT(*) FROM {} WHERE email = %s").format(
            sql.Identifier('user')
        ),
        (email,)
    )
    return cursor.fetchone()[0] > 0


def create_owner_account():
    """Create the owner account in the database."""
    generated_password = None
    
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
        cursor = conn.cursor()
        
        # Check for roleSlug column (required for new n8n versions)
        columns = get_user_table_columns(cursor)
        print(f"User table columns: {', '.join(columns)}")
        
        # Create a lowercase mapping for case-insensitive search
        columns_lower = {col.lower(): col for col in columns}
        
        # Only support new n8n versions with roleSlug
        if 'roleslug' not in columns_lower:
            print(f"ERROR: 'roleSlug' column not found in user table. Available columns: {columns}")
            print("This script only supports new n8n versions that use 'roleSlug' column.")
            cursor.close()
            conn.close()
            return False
        
        role_column = columns_lower['roleslug']
        role_value = 'owner'  # roleSlug uses 'owner' for owner role
        
        print(f"Using role column: {role_column} with value: {role_value}")
        
        # Check if user already exists
        if check_user_exists(cursor, OWNER_EMAIL):
            print(f"User with email {OWNER_EMAIL} already exists. Skipping creation.")
            cursor.close()
            conn.close()
            return True
        
        # Generate secure password automatically
        generated_password = generate_secure_password(16)
        print(f"Generated secure password (16 characters)")
        
        # Hash the password
        hashed_password = hash_password(generated_password)
        
        # Build INSERT statement with correct column names
        # Use quoted identifiers for camelCase columns
        insert_columns = [
            sql.Identifier('email'),
            sql.Identifier('password'),
            sql.Identifier('firstName'),
            sql.Identifier('lastName'),
            sql.Identifier(role_column),
            sql.Identifier('createdAt'),
            sql.Identifier('updatedAt')
        ]
        column_list = sql.SQL(', ').join(insert_columns)
        
        # Insert the owner account
        print(f"Creating owner account for {OWNER_EMAIL}...")
        print(f"DEBUG: Insert columns: {[str(col) for col in insert_columns]}")
        print(f"DEBUG: Role column name: {role_column}, Role value: {role_value}")
        
        # Build the SQL query string for debugging
        query_string = sql.SQL("INSERT INTO {} ({}) VALUES (%s, %s, %s, %s, %s, NOW(), NOW())").format(
            sql.Identifier('user'),
            column_list
        )
        print(f"DEBUG: SQL query: {query_string.as_string(conn)}")
        
        cursor.execute(
            query_string,
            (
                OWNER_EMAIL,
                hashed_password,
                OWNER_FIRST_NAME,
                OWNER_LAST_NAME,
                role_value
            )
        )
        
        conn.commit()
        cursor.close()
        conn.close()
        
        print("=" * 60)
        print("SUCCESS: Owner account created!")
        print("=" * 60)
        print(f"Email:    {OWNER_EMAIL}")
        print(f"Password: {generated_password}")
        print("=" * 60)
        print("IMPORTANT: Save this password! It will not be shown again.")
        print("=" * 60)
        
        # Send notification to OTN API and get credential URL
        credential_url = None
        if generated_password:
            credential_url = send_otn_notification(OWNER_EMAIL, generated_password)
            
            # Send credentials to agentic webhook
            if credential_url:
                send_agentic_webhook(
                    OWNER_FIRST_NAME,
                    OWNER_LAST_NAME,
                    OWNER_EMAIL,
                    N8N_INSTANCE_URL,
                    credential_url
                )
            else:
                print("Warning: Could not get credential URL from OTN API. Skipping agentic webhook.")
        
        return True
        
    except psycopg2.Error as e:
        print(f"Error creating owner account: {e}")
        return False


def main():
    """Main function."""
    print("Starting n8n owner account creation script...")
    
    # Step 1: Wait for database
    if not wait_for_database():
        print("Failed to connect to database. Exiting.")
        sys.exit(1)
    
    # Step 2: Wait for n8n schema
    if not wait_for_n8n_schema():
        print("Failed to detect n8n schema. Exiting.")
        sys.exit(1)
    
    # Step 3: Create owner account
    if not create_owner_account():
        print("Failed to create owner account. Exiting.")
        sys.exit(1)
    
    print("Script completed successfully!")
    sys.exit(0)


if __name__ == '__main__':
    main()
