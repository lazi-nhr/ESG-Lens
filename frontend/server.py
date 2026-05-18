"""
Reverse-proxy frontend server.

This server does two jobs:
  1. Serves static files (index.html, etc.) for browser requests.
  2. Acts as a *reverse proxy* for API paths (/health, /documents, /query):
     it receives the request from the browser, forwards it to the backend
     over the Nuvolos internal network, and returns the backend's response.

Why proxy?  The backend runs on an internal hostname that only exists inside
the Nuvolos network.  The browser (on the public internet) can't reach it
directly, so this server bridges the gap.

    Browser ──► this server (port 3000) ──► backend (internal:8500)
"""
from http.server import HTTPServer, SimpleHTTPRequestHandler
import os
import json
import urllib.request
import urllib.error
import logging


# -- Activate .env variables from .env file (if it exists) ---
from dotenv import load_dotenv
load_dotenv()


# ── Logging configuration ─────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/tmp/frontend.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ── Backend URL ──────────────────────────────────────────────────────────
# The backend lives on the Nuvolos internal network (or localhost for local dev).
# This URL is set via the BACKEND_URL environment variable.
# The browser never sees this URL (it only talks to this reverse proxy).
BACKEND_URL = os.getenv('BACKEND_URL', 'localhost:8500')
if not BACKEND_URL.startswith('http'):
    BACKEND_URL = f'http://{BACKEND_URL}'

class StaticFileHandler(SimpleHTTPRequestHandler):
    """Serves static files and reverse-proxies API paths to the backend."""
    
    def end_headers(self):
        # Disable caching for HTML so the browser always gets the latest version.
        if self.path.endswith('.html') or self.path == '/':
            self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
            self.send_header('Pragma', 'no-cache')
            self.send_header('Expires', '0')
        SimpleHTTPRequestHandler.end_headers(self)
    
    # ── Reverse proxy ────────────────────────────────────────────────────
    # When the browser hits an API path (e.g. /documents), we build the
    # equivalent URL on the backend, forward the request, and pipe the
    # response back.  The browser never knows the backend exists.

    def proxy_to_backend(self, method):
        """Forward a request to the backend and relay its response."""
        try:
            backend_url = f"{BACKEND_URL}{self.path}"
            logger.info(f"{method} {self.path} → {backend_url}")
            
            # Read request body for POST requests
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length) if content_length > 0 else None
            
            # Create the request
            req = urllib.request.Request(backend_url, data=body, method=method)
            
            # Forward relevant headers
            for header in ['Content-Type', 'Authorization']:
                if header in self.headers:
                    req.add_header(header, self.headers[header])
            
            # Make the request to backend
            with urllib.request.urlopen(req) as response:
                # Send response status
                self.send_response(response.status)
                logger.info(f"Backend returned {response.status}")
                
                # Forward response headers
                for header, value in response.headers.items():
                    if header.lower() not in ['connection', 'transfer-encoding']:
                        self.send_header(header, value)
                self.end_headers()
                
                # Forward response body
                self.wfile.write(response.read())
                
        except urllib.error.HTTPError as e:
            # Forward HTTP errors from backend
            logger.warning(f"Backend returned HTTP {e.code}: {e.reason}")
            self.send_response(e.code)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            error_body = e.read()
            self.wfile.write(error_body)
        except Exception as e:
            # Handle other errors
            logger.error(f"Error proxying request: {type(e).__name__}: {e}")
            self.send_response(502)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            error_response = json.dumps({'error': 'Bad Gateway', 'detail': str(e)})
            self.wfile.write(error_response.encode())
    
    def do_GET(self):
        """Serve static files, or reverse-proxy API paths to the backend."""
        path_without_query = self.path.split('?')[0]
        
        # API paths → forward to backend
      
        if (path_without_query == '/health' or 
            path_without_query.startswith('/documents') or 
            path_without_query.startswith('/query') or
            path_without_query.startswith('/companies')): # <--- ADD THIS LINE
            self.proxy_to_backend('GET')
            return

        # Everything else → serve as a static file
        if self.path == '/':
            self.path = '/index.html'

        # For HTML files, serve normally (no injection needed since we're proxying)
        if self.path.endswith('.html'):
            try:
                file_path = self.path.lstrip('/')
                if os.path.exists(file_path):
                    with open(file_path, 'rb') as f:
                        content = f.read()

                    # Send response
                    self.send_response(200)
                    self.send_header('Content-Type', 'text/html; charset=utf-8')
                    self.send_header('Content-Length', len(content))
                    self.end_headers()
                    self.wfile.write(content)
                else:
                    self.send_error(404, "File not found")
            except Exception as e:
                print(f"Error serving HTML file: {e}")
                self.send_error(500, str(e))
        else:
            # For non-HTML files, serve normally
            super().do_GET()
    
    def do_POST(self):
        """Reverse-proxy POST requests (document uploads, queries) to backend."""
        path_without_query = self.path.split('?')[0]
        if (path_without_query.startswith('/documents') or 
            path_without_query.startswith('/query') or
            path_without_query.startswith('/evaluate')):
            self.proxy_to_backend('POST')
        else:
            self.send_response(404)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            error_response = json.dumps({'error': 'Not found'})
            self.wfile.write(error_response.encode())

    def do_OPTIONS(self):
        """Handle CORS preflight requests."""
        path_without_query = self.path.split('?')[0]
        if ('/documents' in path_without_query or 
            '/query' in path_without_query or
            '/evaluate' in path_without_query or
            '/companies' in path_without_query): # <-- Added here too!
            self.send_response(200)
            # ... rest of the code stays the same
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
            self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
            self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()


def run_server(port=None):
    """Run the frontend server."""
    if port is None:
        port = int(os.getenv('FRONTEND_PORT', '3000'))
        
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    
    server_address = ('', port)
    httpd = HTTPServer(server_address, StaticFileHandler)
    
    logger.info(f"Frontend server starting on http://localhost:{port}")
    logger.info(f"Backend URL: {BACKEND_URL}")
    logger.info(f"Serving files from: {os.getcwd()}")
    logger.info("Press Ctrl+C to stop the server")
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down server...")
        httpd.shutdown()


if __name__ == '__main__':
    run_server()
