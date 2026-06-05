"""
Configuration and environment variables.
"""
import os

# Load environment variables from .env file (if it exists)
from dotenv import load_dotenv
load_dotenv()

# Frontend configuration
FRONTEND_PORT = os.getenv("FRONTEND_PORT", "3000")
# BACKEND_URL should be the address the frontend uses to connect to backend
# (not BACKEND_HOST which is for server binding)w
BACKEND_URL = os.getenv("BACKEND_URL", "localhost:8500")
# Chars per second for generating typing effect in frontend
CHARS_PER_SECOND = int(os.getenv("CHARS_PER_SECOND", "200"))