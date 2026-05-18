#!/usr/bin/env python3
"""
Setup script for RAG application
This script:
1. Checks database connection
2. Starts backend server
3. Starts frontend server
"""

import os
import sys
import time
import subprocess
import requests
import psycopg2
from pathlib import Path

# Load environment variables from .env file (if it exists)
from dotenv import load_dotenv
load_dotenv()

# Colors for output
GREEN = '\033[0;32m'
YELLOW = '\033[1;33m'
RED = '\033[0;31m'
NC = '\033[0m'  # No Color

# Database configuration from environment or defaults
DB_HOST = os.getenv("DB_HOST", "nv-service-b48efcd4fbe8cf4a875a2ccb70e0e21b")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "nuvolos")
DB_USER = os.getenv("DB_USER", "nuvolos")
DB_PASSWORD = os.getenv("DB_PASSWORD", "nuvolos")

# Backend configuration
BACKEND_URL = os.getenv("BACKEND_URL", "localhost")
BACKEND_PORT = os.getenv("BACKEND_PORT", "8500")

# Frontend configuration
FRONTEND_PORT = os.getenv("FRONTEND_PORT", "3000")

# Paths
SCRIPT_DIR = Path(__file__).parent.absolute()
BACKEND_DIR = SCRIPT_DIR / "backend"
FRONTEND_DIR = SCRIPT_DIR / "frontend"
PID_DIR = Path("/tmp")
BACKEND_PID_FILE = PID_DIR / "rag_backend.pid"
FRONTEND_PID_FILE = PID_DIR / "rag_frontend.pid"
BACKEND_LOG_FILE = PID_DIR / "backend.log"
FRONTEND_LOG_FILE = PID_DIR / "frontend.log"


def print_colored(color, message):
    """Print colored message."""
    print(f"{color}{message}{NC}")


def print_header(message):
    """Print section header."""
    print_colored(YELLOW, f"\n{message}")


def print_success(message):
    """Print success message."""
    print_colored(GREEN, f"✓ {message}")


def print_error(message):
    """Print error message."""
    print_colored(RED, f"✗ {message}")


def build_backend_url(url_or_host, port, include_scheme=True):
    """Build properly formatted backend URL from host/port."""
    if url_or_host.startswith("http://") or url_or_host.startswith("https://"):
        scheme_end = url_or_host.find("://") + 3
        host_part = url_or_host[scheme_end:]
    else:
        host_part = url_or_host
    
    if ":" in host_part:
        base = host_part
    else:
        base = f"{host_part}:{port}"
    
    if include_scheme and not base.startswith("http://"):
        base = f"http://{base}"
    
    return base


def check_database_connection():
    """Check if database is accessible."""
    print_header("Checking database connection...")
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
        conn.close()
        print_success("Database connection successful\n")
        return True
    except Exception as e:
        print_error("Cannot connect to database")
        print(f"Error: {e}")
        return False


def check_database_content():
    """Check and display database content information."""
    print_header("Database content:")
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
        cur = conn.cursor()
        
        # Check documents table
        try:
            cur.execute("SELECT COUNT(*) FROM documents")
            doc_count = cur.fetchone()[0]
            print(f"  Documents: {doc_count}")
        except Exception as e:
            print("  Documents: (table not found)")
            print(f"    Error: {type(e).__name__}: {str(e)}")
        
        # Check companies table
        try:
            cur.execute("SELECT COUNT(*) FROM companies")
            comp_count = cur.fetchone()[0]
            print(f"  Companies: {comp_count}")
        except Exception as e:
            print("  Companies: (table not found)")
            print(f"    Error: {type(e).__name__}: {str(e)}")
        
        # List tables
        try:
            cur.execute("""
                SELECT table_name FROM information_schema.tables 
                WHERE table_schema='public' AND table_type='BASE TABLE'
                ORDER BY table_name
            """)
            tables = [row[0] for row in cur.fetchall()]
            if tables:
                print(f"  Tables: {', '.join(tables)}")
        except Exception:
            pass
        
        cur.close()
        conn.close()
        print()
        return True
    except Exception as e:
        print(f"  Error checking content: {type(e).__name__}: {str(e)}\n")
        return False


def wait_for_backend(timeout=60):
    """Wait for backend to be ready."""
    print("Waiting for backend to be ready...")
    base_url = build_backend_url(BACKEND_URL, BACKEND_PORT, include_scheme=True)
    backend_url = f"{base_url}/health"
    
    for i in range(timeout):
        try:
            response = requests.get(backend_url, timeout=2)
            if response.status_code == 200:
                print_success("Backend is ready\n")
                return True
        except requests.exceptions.RequestException:
            if i % 15 == 0 and i > 0:
                print(f"  Still waiting ({i}/{timeout}s)...")
        time.sleep(1)
    
    print_error(f"Backend failed to start within {timeout} seconds")
    return False


def start_servers():
    """Start backend and frontend servers."""
    print_header("Starting servers...")
    
    # Start backend
    print(f"Starting backend on port {BACKEND_PORT}...")
    backend_log = open(BACKEND_LOG_FILE, 'w')
    backend_process = subprocess.Popen(
        [sys.executable, "main.py"],
        cwd=BACKEND_DIR,
        stdout=backend_log,
        stderr=subprocess.STDOUT,
        env={**os.environ, **{
            "DB_HOST": DB_HOST,
            "DB_PORT": DB_PORT,
            "DB_NAME": DB_NAME,
            "DB_USER": DB_USER,
            "DB_PASSWORD": DB_PASSWORD
        }}
    )
    BACKEND_PID_FILE.write_text(str(backend_process.pid))
    print_success(f"Backend started (PID: {backend_process.pid})")
    
    # Wait for backend to be ready
    if not wait_for_backend():
        return False
    
    # Start frontend
    print(f"Starting frontend on port {FRONTEND_PORT}...")
    frontend_log = open(FRONTEND_LOG_FILE, 'w')
    backend_host_port = build_backend_url(BACKEND_URL, BACKEND_PORT, include_scheme=False)
    frontend_process = subprocess.Popen(
        [sys.executable, "server.py"],
        cwd=FRONTEND_DIR,
        stdout=frontend_log,
        stderr=subprocess.STDOUT,
        env={**os.environ, **{"BACKEND_URL": backend_host_port}}
    )
    FRONTEND_PID_FILE.write_text(str(frontend_process.pid))
    time.sleep(2)
    
    if frontend_process.poll() is None:
        print_success(f"Frontend started (PID: {frontend_process.pid})\n")
        return True
    else:
        print_error("Frontend failed to start")
        return False


def main():
    """Main setup function."""
    print_colored(GREEN, "=== RAG Application Setup ===\n")
    
    # Check database
    if not check_database_connection():
        sys.exit(1)
    
    # Show database content
    check_database_content()
    
    # Start servers
    if not start_servers():
        sys.exit(1)
    
    # Success
    print_colored(GREEN, "=== Setup Complete! ===\n")
    api_url = build_backend_url(BACKEND_URL, BACKEND_PORT, include_scheme=True)
    print(f"Backend API: {api_url}")
    print(f"Frontend UI: http://localhost:{FRONTEND_PORT}")
    print()
    print(f"Logs: tail -f {BACKEND_LOG_FILE}")
    print(f"      tail -f {FRONTEND_LOG_FILE}")
    print()
    print("To stop: python3 cleanup.py")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nSetup interrupted")
        sys.exit(1)
    except Exception as e:
        print_error(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
