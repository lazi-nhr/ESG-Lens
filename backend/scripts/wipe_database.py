#!/usr/bin/env python3
"""
Wipe database script for RAG example application
This script deletes all documents from the database.
"""

import os
import sys
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


def print_colored(color, message):
    """Print colored message."""
    print(f"{color}{message}{NC}")


def print_success(message):
    """Print success message."""
    print_colored(GREEN, f"✓ {message}")


def print_error(message):
    """Print error message."""
    print_colored(RED, f"✗ {message}")


def wipe_database():
    """Delete all documents from the database."""
    print_colored(YELLOW, "=== Database Wipe ===\n")
    
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
        cur = conn.cursor()
        
        # Get current document count
        cur.execute("SELECT COUNT(*) FROM documents")
        count = cur.fetchone()[0]
        print(f"Current documents in database: {count}")
        
        if count > 0:
            # Delete all documents
            cur.execute("DELETE FROM documents")
            conn.commit()
            print_success("Deleted all documents from database")
        else:
            print("Database is already empty")
        
        cur.close()
        conn.close()
        
        print_colored(GREEN, "\n=== Wipe Complete! ===\n")
        
    except Exception as e:
        print_error("Cannot connect to database")
        print(f"Error: {e}")
        print("Database wipe failed. Please check database connection.")
        print(f"  Host: {DB_HOST}")
        print(f"  Port: {DB_PORT}")
        print(f"  Database: {DB_NAME}")
        print(f"  User: {DB_USER}")
        sys.exit(1)


if __name__ == "__main__":
    try:
        wipe_database()
    except KeyboardInterrupt:
        print("\n\nWipe interrupted by user")
        sys.exit(1)
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
