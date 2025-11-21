#!/usr/bin/env python3
"""
OTN (One-Time Notes) notification module for sending credentials.
"""

import requests
import os


def remove_api_from_url(url):
    """
    Remove /api from URL if present.
    Examples:
    - https://otn.go-ecommerce.de/api/notes/... -> https://otn.go-ecommerce.de/notes/...
    - https://otn.go-ecommerce.de/api-docs.php -> https://otn.go-ecommerce.de/-docs.php (unchanged if no /api/)
    
    Args:
        url (str): URL to clean
    
    Returns:
        str: URL with /api removed if present
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


def send_otn_notification(email, password, otn_url=None):
    """
    Send notification to OTN API with user credentials.
    Returns the credential URL from response if successful, None otherwise.
    
    Args:
        email (str): User email address
        password (str): User password
        otn_url (str, optional): OTN API URL. Defaults to environment variable or hardcoded value.
    
    Returns:
        str or None: Credential URL from response if successful, None otherwise
    """
    if otn_url is None:
        otn_url = os.getenv('OTN_URL', 'https://otn.go-ecommerce.de/api-docs.php')
    
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

