#!/usr/bin/env python3
"""
Automatic login script for n8n.
This script logs in to n8n and creates a session cookie.
"""
import os
import sys
import time
import requests
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# n8n configuration
N8N_HOST = os.getenv('N8N_HOST', 'n8n')
N8N_PORT = os.getenv('N8N_PORT', '5678')
N8N_PROTOCOL = os.getenv('N8N_PROTOCOL', 'http')
N8N_BASE_URL = f"{N8N_PROTOCOL}://{N8N_HOST}:{N8N_PORT}"

# Login credentials
N8N_EMAIL = os.getenv('N8N_DEFAULT_EMAIL', 'Ivan.Levshyn@go-ecommerce.de')
N8N_PASSWORD = os.getenv('N8N_DEFAULT_PASSWORD', '05012005 Ivan')

# Cookie storage
COOKIE_FILE = '/tmp/n8n_session_cookie.txt'

def login_to_n8n():
    """Login to n8n and get session cookie."""
    try:
        print(f"Attempting to login to n8n at {N8N_BASE_URL}...")
        
        session = requests.Session()
        login_url = f"{N8N_BASE_URL}/rest/login"
        
        payload = {
            "email": N8N_EMAIL,
            "password": N8N_PASSWORD
        }
        
        response = session.post(login_url, json=payload, timeout=10)
        
        if response.status_code == 200:
            # Get session cookie
            cookies = session.cookies.get_dict()
            if cookies:
                cookie_str = "; ".join([f"{name}={value}" for name, value in cookies.items()])
                
                # Save cookie to file
                with open(COOKIE_FILE, 'w') as f:
                    f.write(cookie_str)
                
                print(f"✓ Successfully logged in! Cookie saved to {COOKIE_FILE}")
                return cookie_str
            else:
                print("⚠ Login successful but no cookie received")
                return None
        else:
            print(f"⚠ Login failed with status {response.status_code}")
            return None
            
    except Exception as e:
        print(f"Error during login: {e}")
        return None

def get_session_cookie():
    """Get session cookie from file or login."""
    # Try to read existing cookie
    if os.path.exists(COOKIE_FILE):
        try:
            with open(COOKIE_FILE, 'r') as f:
                cookie = f.read().strip()
                # Verify cookie is still valid by making a test request
                test_response = requests.get(
                    f"{N8N_BASE_URL}/rest/login",
                    headers={"Cookie": cookie},
                    timeout=5
                )
                if test_response.status_code != 401:
                    return cookie
        except:
            pass
    
    # Cookie not valid, login again
    return login_to_n8n()

class AutoLoginHandler(BaseHTTPRequestHandler):
    """HTTP handler that injects login cookie."""
    
    def _forward_request(self, method='GET'):
        """Forward request to n8n with automatic login cookie."""
        # Get or create session cookie
        cookie = get_session_cookie()
        
        if not cookie:
            # Try to login again
            cookie = login_to_n8n()
            if not cookie:
                self.send_response(503)
                self.send_header('Content-Type', 'text/html')
                self.end_headers()
                self.wfile.write(b'<html><body>Unable to login to n8n. Please try again.</body></html>')
                return
        
        try:
            # Parse the requested path
            parsed_path = urlparse(self.path)
            n8n_url = f"{N8N_BASE_URL}{parsed_path.path}"
            if parsed_path.query:
                n8n_url += f"?{parsed_path.query}"
            
            # Prepare headers
            headers = {
                "Cookie": cookie,
                "User-Agent": self.headers.get('User-Agent', 'Mozilla/5.0'),
            }
            
            # Copy relevant headers
            for header_name in ['Content-Type', 'Accept', 'Accept-Language', 'Referer']:
                if header_name in self.headers:
                    headers[header_name] = self.headers[header_name]
            
            # Read request body for POST/PUT
            body = None
            if method in ['POST', 'PUT', 'PATCH']:
                content_length = int(self.headers.get('Content-Length', 0))
                if content_length > 0:
                    body = self.rfile.read(content_length)
            
            # Forward request to n8n
            if method == 'GET':
                response = requests.get(n8n_url, headers=headers, timeout=30, allow_redirects=False)
            elif method == 'POST':
                response = requests.post(n8n_url, data=body, headers=headers, timeout=30, allow_redirects=False)
            elif method == 'PUT':
                response = requests.put(n8n_url, data=body, headers=headers, timeout=30, allow_redirects=False)
            elif method == 'DELETE':
                response = requests.delete(n8n_url, headers=headers, timeout=30, allow_redirects=False)
            else:
                response = requests.request(method, n8n_url, data=body, headers=headers, timeout=30, allow_redirects=False)
            
            # Forward response
            self.send_response(response.status_code)
            
            # Forward headers (except some that should be handled by proxy)
            skip_headers = ['content-encoding', 'transfer-encoding', 'connection', 'server']
            for header, value in response.headers.items():
                if header.lower() not in skip_headers:
                    self.send_header(header, value)
            
            # Always set the session cookie
            self.send_header('Set-Cookie', cookie)
            
            self.end_headers()
            self.wfile.write(response.content)
            
        except requests.exceptions.RequestException as e:
            print(f"Error forwarding {method} request: {e}")
            self.send_response(502)
            self.send_header('Content-Type', 'text/html')
            self.end_headers()
            self.wfile.write(f'<html><body>Error connecting to n8n: {str(e)}</body></html>'.encode())
        except Exception as e:
            print(f"Unexpected error: {e}")
            self.send_response(500)
            self.end_headers()
            self.wfile.write(b'Internal Server Error')
    
    def do_GET(self):
        """Handle GET requests."""
        self._forward_request('GET')
    
    def do_POST(self):
        """Handle POST requests."""
        self._forward_request('POST')
    
    def do_PUT(self):
        """Handle PUT requests."""
        self._forward_request('PUT')
    
    def do_DELETE(self):
        """Handle DELETE requests."""
        self._forward_request('DELETE')

    def log_message(self, format, *args):
        """Suppress default logging."""
        pass

def main():
    """Main function."""
    print("=" * 50)
    print("n8n Auto-Login Proxy")
    print("=" * 50)
    print(f"n8n URL: {N8N_BASE_URL}")
    print(f"Email: {N8N_EMAIL}")
    print("=" * 50)
    
    # Initial login
    login_to_n8n()
    
    # Start HTTP server
    port = int(os.getenv('PROXY_PORT', '8080'))
    server = HTTPServer(('0.0.0.0', port), AutoLoginHandler)
    print(f"Auto-login proxy started on port {port}")
    print("Ready to forward requests to n8n with automatic login...")
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.shutdown()

if __name__ == "__main__":
    main()

