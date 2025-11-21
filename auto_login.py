#!/usr/bin/env python3
"""
Auto-login proxy for n8n.
Intercepts requests, checks for authentication, and automatically logs in if needed.
"""

import os
import requests
from flask import Flask, request, Response, make_response
from urllib.parse import urljoin
import time

app = Flask(__name__)

# Configuration from environment
N8N_HOST = os.getenv('N8N_HOST', 'n8n')
N8N_PORT = int(os.getenv('N8N_PORT', 5678))
N8N_PROTOCOL = os.getenv('N8N_PROTOCOL', 'http')
N8N_BASE_URL = f"{N8N_PROTOCOL}://{N8N_HOST}:{N8N_PORT}"

EMAIL = os.getenv('N8N_DEFAULT_EMAIL', 'admin@example.com')
PASSWORD = os.getenv('N8N_DEFAULT_PASSWORD', 'changeme')

# Session to maintain cookies
session = requests.Session()
session_cookies = {}
login_attempted = False


def wait_for_n8n():
    """Wait for n8n to be ready."""
    max_retries = 30
    for i in range(max_retries):
        try:
            response = session.get(f"{N8N_BASE_URL}/healthz", timeout=5)
            if response.status_code == 200:
                print("n8n is ready!")
                return True
        except requests.exceptions.RequestException:
            pass
        
        if i < max_retries - 1:
            print(f"Waiting for n8n to be ready... ({i+1}/{max_retries})")
            time.sleep(2)
    
    print("Warning: n8n may not be ready yet, continuing anyway...")
    return False


def auto_login():
    """Automatically log in to n8n and return session cookies."""
    global session_cookies, login_attempted
    
    if login_attempted and session_cookies:
        return session_cookies
    
    try:
        print(f"Attempting to auto-login with email: {EMAIL}")
        
        # Login endpoint
        login_url = f"{N8N_BASE_URL}/rest/login"
        
        login_data = {
            "email": EMAIL,
            "password": PASSWORD
        }
        
        response = session.post(
            login_url,
            json=login_data,
            headers={'Content-Type': 'application/json'},
            timeout=10
        )
        
        if response.status_code == 200:
            # Extract cookies from response
            cookies = response.cookies.get_dict()
            
            # Also check for Set-Cookie headers
            for cookie in response.cookies:
                session_cookies[cookie.name] = cookie.value
            
            # Store session cookies
            session_cookies.update(cookies)
            login_attempted = True
            
            print(f"Successfully logged in! Cookies: {list(session_cookies.keys())}")
            return session_cookies
        else:
            print(f"Login failed with status {response.status_code}: {response.text}")
            return None
            
    except Exception as e:
        print(f"Error during auto-login: {e}")
        return None


def check_authentication(cookies):
    """Check if the provided cookies indicate valid authentication by verifying with n8n API."""
    if not cookies:
        return False
    
    # Check for n8n session cookie (usually 'n8n-auth' or similar)
    auth_cookies = [k for k in cookies.keys() if 'auth' in k.lower() or 'session' in k.lower() or 'n8n' in k.lower()]
    
    if len(auth_cookies) == 0:
        return False
    
    # Verify authentication by checking /rest/me endpoint
    try:
        cookie_header = '; '.join([f"{k}={v}" for k, v in cookies.items()])
        headers = {'Cookie': cookie_header}
        response = session.get(f"{N8N_BASE_URL}/rest/me", headers=headers, timeout=5)
        return response.status_code == 200
    except:
        return False


@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def proxy(path):
    """Proxy all requests to n8n with auto-login."""
    global session_cookies
    
    # Get cookies from incoming request
    incoming_cookies = request.cookies
    
    # Check if user is already authenticated
    is_authenticated = check_authentication(incoming_cookies)
    
    # If not authenticated, try to auto-login
    if not is_authenticated:
        # Always try to auto-login to ensure we have valid session
        auto_login_cookies = auto_login()
        
        if auto_login_cookies:
            # Merge auto-login cookies with incoming cookies (auto-login takes precedence)
            merged_cookies = {**incoming_cookies, **auto_login_cookies}
        else:
            merged_cookies = incoming_cookies
    else:
        merged_cookies = incoming_cookies
        # Update our session cookies from incoming request
        session_cookies.update(incoming_cookies)
    
    # Build the target URL
    if path:
        target_url = urljoin(f"{N8N_BASE_URL}/", path)
    else:
        target_url = N8N_BASE_URL
    
    # Add query string if present
    if request.query_string:
        target_url += f"?{request.query_string.decode('utf-8')}"
    
    # Prepare headers (exclude host and connection)
    headers = {}
    for key, value in request.headers:
        if key.lower() not in ['host', 'connection', 'content-length']:
            headers[key] = value
    
    # Prepare cookies for the request
    cookie_header = '; '.join([f"{k}={v}" for k, v in merged_cookies.items()])
    if cookie_header:
        headers['Cookie'] = cookie_header
    
    try:
        # Forward the request
        if request.method == 'GET':
            resp = session.get(target_url, headers=headers, timeout=30, allow_redirects=False)
        elif request.method == 'POST':
            resp = session.post(
                target_url,
                headers=headers,
                data=request.get_data(),
                timeout=30,
                allow_redirects=False
            )
        elif request.method == 'PUT':
            resp = session.put(
                target_url,
                headers=headers,
                data=request.get_data(),
                timeout=30,
                allow_redirects=False
            )
        elif request.method == 'DELETE':
            resp = session.delete(target_url, headers=headers, timeout=30, allow_redirects=False)
        elif request.method == 'PATCH':
            resp = session.patch(
                target_url,
                headers=headers,
                data=request.get_data(),
                timeout=30,
                allow_redirects=False
            )
        else:
            resp = session.request(
                request.method,
                target_url,
                headers=headers,
                data=request.get_data(),
                timeout=30,
                allow_redirects=False
            )
        
        # Create response
        response = make_response(resp.content, resp.status_code)
        
        # Copy response headers
        for key, value in resp.headers.items():
            if key.lower() not in ['content-encoding', 'transfer-encoding', 'content-length', 'connection']:
                response.headers[key] = value
        
        # Update cookies from response
        for cookie in resp.cookies:
            session_cookies[cookie.name] = cookie.value
            response.set_cookie(
                cookie.name,
                cookie.value,
                max_age=cookie.max_age,
                path=cookie.path,
                domain=None,  # Don't set domain to allow browser to handle it
                secure=cookie.secure,
                httponly=cookie.http_only,
                samesite='Lax'
            )
        
        # Also set our auto-login cookies if they exist
        if not is_authenticated and session_cookies:
            for name, value in session_cookies.items():
                if name not in [c.name for c in resp.cookies]:
                    response.set_cookie(name, value, samesite='Lax')
        
        return response
        
    except Exception as e:
        print(f"Error proxying request: {e}")
        return make_response(f"Proxy error: {str(e)}", 502)


if __name__ == '__main__':
    print(f"Starting auto-login proxy for n8n at {N8N_BASE_URL}")
    print(f"Auto-login email: {EMAIL}")
    
    # Wait for n8n to be ready
    wait_for_n8n()
    
    # Try initial login
    auto_login()
    
    # Start the proxy server
    port = int(os.getenv('PROXY_PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)

