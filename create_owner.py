#!/usr/bin/env python3
"""
Script to create n8n owner account in PostgreSQL database.
Waits for n8n to initialize its database schema, then inserts the owner account.
"""

import os
import sys
import time
import psycopg2
import bcrypt
from psycopg2 import sql

# Database connection parameters
DB_HOST = os.getenv('DB_POSTGRESDB_HOST', 'postgres')
DB_PORT = int(os.getenv('DB_POSTGRESDB_PORT', 5432))
DB_NAME = os.getenv('DB_POSTGRESDB_DATABASE', 'n8n')
DB_USER = os.getenv('DB_POSTGRESDB_USER', 'n8n')
DB_PASSWORD = os.getenv('DB_POSTGRESDB_PASSWORD', 'n8n')

# Owner account details
OWNER_EMAIL = os.getenv('N8N_DEFAULT_EMAIL', 'admin@example.com')
OWNER_PASSWORD = os.getenv('N8N_DEFAULT_PASSWORD', 'changeme')
OWNER_FIRST_NAME = os.getenv('N8N_DEFAULT_FIRST_NAME', 'Admin')
OWNER_LAST_NAME = os.getenv('N8N_DEFAULT_LAST_NAME', 'User')

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


def hash_password(password):
    """Hash password using bcrypt (same as n8n uses)."""
    # n8n uses bcrypt with salt rounds 10
    salt = bcrypt.gensalt(rounds=10)
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')


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
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
        cursor = conn.cursor()
        
        # Check if user already exists
        if check_user_exists(cursor, OWNER_EMAIL):
            print(f"User with email {OWNER_EMAIL} already exists. Skipping creation.")
            cursor.close()
            conn.close()
            return True
        
        # Hash the password
        hashed_password = hash_password(OWNER_PASSWORD)
        
        # Insert the owner account
        print(f"Creating owner account for {OWNER_EMAIL}...")
        cursor.execute(
            sql.SQL("""
                INSERT INTO {} (email, password, "firstName", "lastName", role, "createdAt", "updatedAt")
                VALUES (%s, %s, %s, %s, %s, NOW(), NOW())
            """).format(
                sql.Identifier('user')
            ),
            (
                OWNER_EMAIL,
                hashed_password,
                OWNER_FIRST_NAME,
                OWNER_LAST_NAME,
                'global:owner'
            )
        )
        
        conn.commit()
        cursor.close()
        conn.close()
        
        print(f"Successfully created owner account for {OWNER_EMAIL}!")
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

