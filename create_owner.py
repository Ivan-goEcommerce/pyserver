#!/usr/bin/env python3
"""
Create n8n owner user using n8n CLI.
This script integrates with other Python modules for notifications and webhooks.
"""

import os
import subprocess
import sys
import time


def wait_for_n8n(max_retries=30, delay=2):
    """
    Wait for n8n to be ready by checking if n8n CLI can list users.
    
    Args:
        max_retries (int): Maximum number of retry attempts
        delay (int): Delay between retries in seconds
    
    Returns:
        bool: True if n8n is ready, False otherwise
    """
    print("Waiting for n8n to be ready...")
    for i in range(max_retries):
        try:
            result = subprocess.run(
                ['n8n', 'user', 'list'],
                capture_output=True,
                timeout=5
            )
            if result.returncode == 0:
                print("n8n is ready!")
                return True
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        
        if i < max_retries - 1:
            print(f"n8n is not ready yet, waiting... (attempt {i+1}/{max_retries})")
            time.sleep(delay)
    
    print("n8n did not become ready in time")
    return False


def user_exists(email):
    """
    Check if a user with the given email already exists.
    
    Args:
        email (str): Email address to check
    
    Returns:
        bool: True if user exists, False otherwise
    """
    try:
        result = subprocess.run(
            ['n8n', 'user', 'list'],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            return email in result.stdout
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        print(f"Error checking if user exists: {e}")
    
    return False


def create_user(email, password, first_name, last_name):
    """
    Create a new n8n user using the n8n CLI.
    
    Args:
        email (str): User email address
        password (str): User password
        first_name (str): User's first name
        last_name (str): User's last name
    
    Returns:
        bool: True if user was created successfully, False otherwise
    """
    try:
        print(f"Creating owner user: {email}")
        result = subprocess.run(
            [
                'n8n', 'user', 'create',
                '--email', email,
                '--password', password,
                '--firstName', first_name,
                '--lastName', last_name
            ],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0:
            print("Owner user created successfully!")
            return True
        else:
            print(f"Error creating user: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        print("Timeout while creating user")
        return False
    except FileNotFoundError:
        print("n8n CLI not found. Make sure n8n is installed and in PATH.")
        return False
    except Exception as e:
        print(f"Unexpected error creating user: {e}")
        return False


def main():
    """Main function to create n8n owner user."""
    # Get environment variables
    email = os.getenv('N8N_DEFAULT_EMAIL')
    password = os.getenv('N8N_DEFAULT_PASSWORD', 'changeme')
    first_name = os.getenv('N8N_DEFAULT_FIRST_NAME', 'Admin')
    last_name = os.getenv('N8N_DEFAULT_LAST_NAME', 'User')
    
    # Validate required environment variables
    if not email:
        print("Error: N8N_DEFAULT_EMAIL environment variable is required")
        sys.exit(1)
    
    # Wait for n8n to be ready
    if not wait_for_n8n():
        print("Failed to connect to n8n. Exiting.")
        sys.exit(1)
    
    # Check if user already exists
    if user_exists(email):
        print(f"Owner user {email} already exists, skipping creation.")
        sys.exit(0)
    
    # Create the user
    if create_user(email, password, first_name, last_name):
        # Here you can integrate with other Python modules if needed
        # For example, send notifications or webhooks
        n8n_url = os.getenv('N8N_INSTANCE_URL')
        if n8n_url:
            # Import and use other modules if needed
            try:
                from otn_notification import send_otn_notification
                from agentic_webhook import send_agentic_webhook
                
                # Send OTN notification
                credential_url = send_otn_notification(email, password)
                
                # Send agentic webhook if credential URL was received
                if credential_url:
                    send_agentic_webhook(
                        first_name=first_name,
                        last_name=last_name,
                        email=email,
                        n8n_url=n8n_url,
                        credential_url=credential_url
                    )
            except ImportError as e:
                print(f"Note: Could not import notification modules: {e}")
            except Exception as e:
                print(f"Note: Error sending notifications: {e}")
        
        sys.exit(0)
    else:
        print("Failed to create owner user.")
        sys.exit(1)


if __name__ == '__main__':
    main()

