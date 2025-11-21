#!/usr/bin/env python3
"""
Script to create n8n owner account in PostgreSQL database.
Waits for n8n to initialize its database schema, then inserts the owner account.
"""

import os
import sys
import time
import secrets
import string
import requests
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
OWNER_FIRST_NAME = os.getenv('N8N_DEFAULT_FIRST_NAME', 'Admin')
OWNER_LAST_NAME = os.getenv('N8N_DEFAULT_LAST_NAME', 'User')
N8N_INSTANCE_URL = os.getenv('N8N_INSTANCE_URL', 'http://n8n-ivan.go-ecommerce.de/')
# Password will be auto-generated (16 characters with uppercase, lowercase, digit, special char)

# Agentic webhook configuration
AGENTIC_ACCESS_KEY = os.getenv('AGENTIC_ACCESS_KEY', 'aG7pL9xQ2vR4cT1w#Z8mK3bN6yH0fD5-')
AGENTIC_APPLICATION = os.getenv('AGENTIC_APPLICATION', 'go-eCommerce-n8n-hosting')

MAX_RETRIES = 30
RETRY_DELAY = 2


def generate_secure_password(length=16):
    """
    Generate a secure random password with:
    - Uppercase letters
    - Lowercase letters
    - Digits
    - Special characters
    """
    # Define character sets
    uppercase = string.ascii_uppercase
    lowercase = string.ascii_lowercase
    digits = string.digits
    special = "!@#$%^&*()_+-=[]{}|;:,.<>?"
    
    # Ensure at least one character from each category
    password_chars = [
        secrets.choice(uppercase),
        secrets.choice(lowercase),
        secrets.choice(digits),
        secrets.choice(special)
    ]
    
    # Fill the rest with random characters from all sets
    all_chars = uppercase + lowercase + digits + special
    for _ in range(length - 4):
        password_chars.append(secrets.choice(all_chars))
    
    # Shuffle to avoid predictable pattern
    secrets.SystemRandom().shuffle(password_chars)
    
    return ''.join(password_chars)


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


def remove_api_from_url(url):
    """
    Remove /api from URL if present.
    Examples:
    - https://otn.go-ecommerce.de/api/notes/... -> https://otn.go-ecommerce.de/notes/...
    - https://otn.go-ecommerce.de/api-docs.php -> https://otn.go-ecommerce.de/-docs.php (unchanged if no /api/)
    """
    if "/api/" in url:
        # Replace /api/ with /
        url = url.replace("/api/", "/")
    elif url.endswith("/api"):
        # Remove /api at the end
        url = url[:-4]
    elif "/api" in url and not url.endswith("/api"):
        # Handle /api followed by something (like /api/notes or /api?param=value)
        # Replace first occurrence of /api with empty string
        url = url.replace("/api", "", 1)
    return url


def send_otn_notification(email, password):
    """
    Send notification to OTN API with user credentials.
    Returns the credential URL from response if successful, None otherwise.
    """
    otn_url = "https://otn.go-ecommerce.de/api-docs.php"
    
    # Remove /api from URL if present
    otn_url_cleaned = remove_api_from_url(otn_url)
    
    message = f"benutzername: {email}\nKennwort: {password}"
    payload = {"message": message}
    
    try:
        print(f"Sending notification to OTN API: {otn_url_cleaned}")
        response = requests.post(
            otn_url_cleaned,
            json=payload,
            headers={'Content-Type': 'application/json'},
            timeout=10
        )
        
        if response.status_code == 200:
            print(f"Successfully sent notification to OTN API")
            
            # Try to extract credential URL from response
            credential_url = None
            try:
                response_data = response.json()
                # Try different possible fields in the response
                if 'url' in response_data:
                    credential_url = response_data['url']
                elif 'credential_url' in response_data:
                    credential_url = response_data['credential_url']
                elif 'link' in response_data:
                    credential_url = response_data['link']
                elif isinstance(response_data, str):
                    # Response might be a URL string
                    credential_url = response_data
            except:
                # If response is not JSON, check if it's a URL in text
                response_text = response.text.strip()
                if response_text.startswith('http'):
                    credential_url = response_text
            
            # If no URL found in response, use the OTN base URL
            if not credential_url:
                credential_url = otn_url_cleaned
            
            # Remove /api from credential URL if present
            credential_url = remove_api_from_url(credential_url)
            
            return credential_url
        else:
            print(f"OTN API returned status {response.status_code}: {response.text}")
            return None
            
    except requests.exceptions.RequestException as e:
        print(f"Error sending notification to OTN API: {e}")
        return None


def send_agentic_webhook(first_name, last_name, email, n8n_url, credential_url):
    """Send credentials to agentic webhook."""
    agentic_url = "https://agentic.go-ecommerce.de/webhook/v1/credentials"
    
    headers = {
        "X-Access-Key": AGENTIC_ACCESS_KEY,
        "X-Application": AGENTIC_APPLICATION,
        "Content-Type": "application/json"
    }
    
    payload = {
        "first_name": first_name,
        "name": last_name,
        "mail": email,
        "n8n_instanceurl": n8n_url.rstrip('/') + '/',  # Ensure trailing slash
        "credentials": [
            {
                "credential_url": credential_url
            }
        ]
    }
    
    try:
        print(f"Sending credentials to agentic webhook: {agentic_url}")
        response = requests.post(
            agentic_url,
            json=payload,
            headers=headers,
            timeout=10
        )
        
        if response.status_code in [200, 201]:
            print(f"Successfully sent credentials to agentic webhook")
            return True
        else:
            print(f"Agentic webhook returned status {response.status_code}: {response.text}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"Error sending credentials to agentic webhook: {e}")
        return False


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
        
        # Check if user already exists
        if check_user_exists(cursor, OWNER_EMAIL):
            print(f"User with email {OWNER_EMAIL} already exists. Skipping creation.")
            cursor.close()
            conn.close()
            return True
        
        # Get all columns from user table to find correct column names
        columns = get_user_table_columns(cursor)
        print(f"Found columns in user table: {', '.join(columns)}")
        
        # Map column names (handle different n8n versions)
        email_col = 'email'
        password_col = 'password'
        first_name_col = 'firstName' if 'firstName' in columns else ('first_name' if 'first_name' in columns else None)
        last_name_col = 'lastName' if 'lastName' in columns else ('last_name' if 'last_name' in columns else None)
        role_col = None
        for col in ['globalRole', 'role', 'roles']:
            if col in columns:
                role_col = col
                break
        
        created_at_col = 'createdAt' if 'createdAt' in columns else ('created_at' if 'created_at' in columns else None)
        updated_at_col = 'updatedAt' if 'updatedAt' in columns else ('updated_at' if 'updated_at' in columns else None)
        
        if not first_name_col or not last_name_col:
            raise Exception(f"Could not find firstName/lastName columns. Available columns: {columns}")
        
        # Generate secure password automatically
        generated_password = generate_secure_password(16)
        print(f"Generated secure password (16 characters)")
        
        # Hash the password
        hashed_password = hash_password(generated_password)
        
        # Build INSERT statement dynamically based on available columns
        insert_cols = []
        placeholders = []
        insert_values = []
        
        # Add required columns
        insert_cols.append(email_col)
        placeholders.append('%s')
        insert_values.append(OWNER_EMAIL)
        
        insert_cols.append(password_col)
        placeholders.append('%s')
        insert_values.append(hashed_password)
        
        insert_cols.append(first_name_col)
        placeholders.append('%s')
        insert_values.append(OWNER_FIRST_NAME)
        
        insert_cols.append(last_name_col)
        placeholders.append('%s')
        insert_values.append(OWNER_LAST_NAME)
        
        if role_col:
            insert_cols.append(role_col)
            placeholders.append('%s')
            # n8n uses 'global:owner' or just 'owner' depending on version
            role_value = 'global:owner' if role_col == 'globalRole' else 'owner'
            insert_values.append(role_value)
        
        if created_at_col:
            insert_cols.append(created_at_col)
            placeholders.append('NOW()')
            # No value needed for NOW()
        
        if updated_at_col:
            insert_cols.append(updated_at_col)
            placeholders.append('NOW()')
            # No value needed for NOW()
        
        # Build column names with proper quoting
        col_names = []
        for col in insert_cols:
            if col in ['firstName', 'lastName', 'createdAt', 'updatedAt', 'globalRole']:
                col_names.append(f'"{col}"')
            else:
                col_names.append(col)
        
        # Insert the owner account
        print(f"Creating owner account for {OWNER_EMAIL}...")
        print(f"Using columns: {insert_cols}")
        
        # Build query
        col_names_str = ', '.join(col_names)
        placeholders_str = ', '.join(placeholders)
        query = f'INSERT INTO "user" ({col_names_str}) VALUES ({placeholders_str})'
        
        cursor.execute(query, insert_values)
        
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

