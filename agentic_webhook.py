#!/usr/bin/env python3
"""
Agentic webhook module for sending credentials.
"""

import requests
import os


def send_agentic_webhook(first_name, last_name, email, n8n_url, credential_url, 
                        access_key=None, application=None):
    """
    Send credentials to agentic webhook.
    
    Args:
        first_name (str): User's first name
        last_name (str): User's last name
        email (str): User's email address
        n8n_url (str): n8n instance URL
        credential_url (str): Credential URL from OTN
        access_key (str, optional): Access key for webhook. Defaults to environment variable.
        application (str, optional): Application name. Defaults to environment variable.
    
    Returns:
        bool: True if successful, False otherwise
    """
    agentic_url = os.getenv('AGENTIC_WEBHOOK_URL', 'https://agentic.go-ecommerce.de/webhook/v1/credentials')
    
    if access_key is None:
        access_key = os.getenv('AGENTIC_ACCESS_KEY', 'aG7pL9xQ2vR4cT1w#Z8mK3bN6yH0fD5-')
    
    if application is None:
        application = os.getenv('AGENTIC_APPLICATION', 'go-eCommerce-n8n-hosting')
    
    headers = {
        "X-Access-Key": access_key,
        "X-Application": application,
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

