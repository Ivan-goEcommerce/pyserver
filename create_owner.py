#!/usr/bin/env python3
"""
Script to automatically create an owner account in n8n PostgreSQL database.
This script waits for the database to be ready, then creates the owner user.
"""

import os
import sys
import time
import psycopg2
from psycopg2 import sql
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from password_utils import hash_password
from otn_notification import send_otn_notification
from agentic_webhook import send_agentic_webhook


def wait_for_database(max_retries=30, retry_delay=2):
    """
    Wait for PostgreSQL database to be ready.
    
    Args:
        max_retries (int): Maximum number of retry attempts
        retry_delay (int): Delay between retries in seconds
    
    Returns:
        bool: True if database is ready, False otherwise
    """
    db_config = {
        'host': os.getenv('POSTGRES_HOST', 'postgres'),
        'port': os.getenv('POSTGRES_PORT', '5432'),
        'database': os.getenv('POSTGRES_DB', 'n8n'),
        'user': os.getenv('POSTGRES_USER', 'n8n'),
        'password': os.getenv('POSTGRES_PASSWORD', 'n8n')
    }
    
    print(f"Waiting for PostgreSQL database at {db_config['host']}:{db_config['port']}...")
    
    for attempt in range(max_retries):
        try:
            conn = psycopg2.connect(**db_config)
            conn.close()
            print("Database is ready!")
            return True
        except psycopg2.OperationalError as e:
            if attempt < max_retries - 1:
                print(f"Attempt {attempt + 1}/{max_retries}: Database not ready yet, retrying in {retry_delay}s...")
                time.sleep(retry_delay)
            else:
                print(f"Failed to connect to database after {max_retries} attempts: {e}")
                return False
    
    return False


def wait_for_n8n_tables(max_retries=60, retry_delay=5):
    """
    Wait for n8n to initialize its database tables.
    
    Args:
        max_retries (int): Maximum number of retry attempts
        retry_delay (int): Delay between retries in seconds
    
    Returns:
        bool: True if tables exist, False otherwise
    """
    db_config = {
        'host': os.getenv('POSTGRES_HOST', 'postgres'),
        'port': os.getenv('POSTGRES_PORT', '5432'),
        'database': os.getenv('POSTGRES_DB', 'n8n'),
        'user': os.getenv('POSTGRES_USER', 'n8n'),
        'password': os.getenv('POSTGRES_PASSWORD', 'n8n')
    }
    
    print("Waiting for n8n to initialize database tables...")
    
    for attempt in range(max_retries):
        try:
            conn = psycopg2.connect(**db_config)
            cursor = conn.cursor()
            
            # Check if user table exists (n8n uses 'user' table in public schema)
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
                print("n8n database tables are ready!")
                return True
            else:
                if attempt < max_retries - 1:
                    print(f"Attempt {attempt + 1}/{max_retries}: Tables not ready yet, retrying in {retry_delay}s...")
                    time.sleep(retry_delay)
                else:
                    print(f"n8n tables not found after {max_retries} attempts")
                    return False
                    
        except psycopg2.Error as e:
            if attempt < max_retries - 1:
                print(f"Attempt {attempt + 1}/{max_retries}: Error checking tables: {e}, retrying in {retry_delay}s...")
                time.sleep(retry_delay)
            else:
                print(f"Failed to check for tables after {max_retries} attempts: {e}")
                return False
    
    return False


def check_user_exists(cursor, email):
    """
    Check if a user with the given email already exists.
    
    Args:
        cursor: Database cursor
        email (str): Email address to check
    
    Returns:
        bool: True if user exists, False otherwise
    """
    try:
        cursor.execute("SELECT id FROM public.user WHERE email = %s", (email,))
        return cursor.fetchone() is not None
    except psycopg2.Error as e:
        print(f"Error checking if user exists: {e}")
        return False


def create_owner_user():
    """
    Create an owner user in the n8n database.
    """
    # Get configuration from environment variables
    email = os.getenv('N8N_DEFAULT_EMAIL')
    first_name = os.getenv('N8N_DEFAULT_FIRST_NAME', 'Admin')
    last_name = os.getenv('N8N_DEFAULT_LAST_NAME', 'User')
    password = os.getenv('N8N_DEFAULT_PASSWORD', 'changeme')
    n8n_url = os.getenv('N8N_INSTANCE_URL', 'https://n8n-ivan.go-ecommerce.de/')
    
    if not email:
        print("Error: N8N_DEFAULT_EMAIL environment variable is not set")
        sys.exit(1)
    
    db_config = {
        'host': os.getenv('POSTGRES_HOST', 'postgres'),
        'port': os.getenv('POSTGRES_PORT', '5432'),
        'database': os.getenv('POSTGRES_DB', 'n8n'),
        'user': os.getenv('POSTGRES_USER', 'n8n'),
        'password': os.getenv('POSTGRES_PASSWORD', 'n8n')
    }
    
    print(f"Checking for owner user: {email}")
    print(f"First Name: {first_name}, Last Name: {last_name}")
    
    # Wait for database to be ready
    if not wait_for_database():
        print("Failed to connect to database")
        sys.exit(1)
    
    # Wait for n8n tables to be initialized
    if not wait_for_n8n_tables():
        print("Failed to find n8n database tables")
        sys.exit(1)
    
    try:
        # Connect to database
        conn = psycopg2.connect(**db_config)
        cursor = conn.cursor()
        
        # Check if user already exists
        if check_user_exists(cursor, email):
            print(f"User with email {email} already exists. Skipping creation.")
            cursor.close()
            conn.close()
            return
        
        # User doesn't exist, proceed with creation
        print(f"Creating owner user: {email}")
        
        # Hash the password using bcrypt (same as n8n uses)
        hashed_password = hash_password(password)
        print("Password hashed successfully")
        
        # Get the current timestamp
        from datetime import datetime
        now = datetime.utcnow()
        
        # Insert the owner user
        # For newest n8n version, the user table structure includes:
        # - id (uuid, auto-generated)
        # - email (unique)
        # - password (bcrypt hashed)
        # - firstName
        # - lastName
        # - globalRole (for owner: 'global:owner')
        # - createdAt
        # - updatedAt
        
        # Check table structure first to determine which columns exist
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_schema = 'public' 
            AND table_name = 'user'
            ORDER BY ordinal_position;
        """)
        columns = [row[0] for row in cursor.fetchall()]
        print(f"User table columns: {columns}")
        
        # Build INSERT statement based on available columns
        # Newest n8n versions use 'globalRole' instead of 'roleSlug'
        if 'globalRole' in columns:
            # Modern n8n structure
            cursor.execute("""
                INSERT INTO public.user (email, password, "firstName", "lastName", "globalRole", "createdAt", "updatedAt")
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (email, hashed_password, first_name, last_name, 'global:owner', now, now))
        elif 'roleSlug' in columns:
            # Older n8n structure
            cursor.execute("""
                INSERT INTO public.user (email, password, "firstName", "lastName", "roleSlug", "createdAt", "updatedAt")
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (email, hashed_password, first_name, last_name, 'global:owner', now, now))
        else:
            # Fallback: try without role column (n8n might set default)
            try:
                cursor.execute("""
                    INSERT INTO public.user (email, password, "firstName", "lastName", "createdAt", "updatedAt")
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (email, hashed_password, first_name, last_name, now, now))
            except psycopg2.Error:
                # If createdAt/updatedAt don't exist, try minimal insert
                cursor.execute("""
                    INSERT INTO public.user (email, password, "firstName", "lastName")
                    VALUES (%s, %s, %s, %s)
                """, (email, hashed_password, first_name, last_name))
        
        conn.commit()
        print(f"Successfully created owner user: {email}")
        
        cursor.close()
        conn.close()
        
        # Send notifications
        print("\nSending notifications...")
        
        # Send OTN notification
        credential_url = send_otn_notification(email, password)
        if credential_url:
            print(f"OTN notification sent. Credential URL: {credential_url}")
        else:
            print("OTN notification failed")
        
        # Send agentic webhook
        if credential_url:
            webhook_success = send_agentic_webhook(
                first_name=first_name,
                last_name=last_name,
                email=email,
                n8n_url=n8n_url,
                credential_url=credential_url
            )
            if webhook_success:
                print("Agentic webhook sent successfully")
            else:
                print("Agentic webhook failed")
        
        print("\nOwner user creation completed successfully!")
        
    except psycopg2.Error as e:
        print(f"Database error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    create_owner_user()

