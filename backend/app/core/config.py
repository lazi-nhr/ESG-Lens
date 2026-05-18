"""
Configuration and environment variables.
"""
import os
from dotenv import load_dotenv

# Load environment variables from .env file (if it exists)
load_dotenv()

# Database
DB_HOST = os.getenv("DB_HOST", "nv-service-b48efcd4fbe8cf4a875a2ccb70e0e21b")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "nuvolos")
DB_USER = os.getenv("DB_USER", "nuvolos")
DB_PASSWORD = os.getenv("DB_PASSWORD", "nuvolos")

# Server
BACKEND_PORT = int(os.getenv("BACKEND_PORT", "8500"))
BACKEND_HOST = os.getenv("BACKEND_HOST", "0.0.0.0")

# Retrieval
EMBEDDING_DIM = 768
DEFAULT_TOP_K = 3
MAX_TOP_K = 100

# LLM / Generation
DEFAULT_FORMAT = "markdown"  # "markdown" | "text"
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "huggingface")

# Hardcoding Falcon-7b-instruct and your API key as direct fallbacks
HF_MODEL = os.getenv("HF_MODEL", "tiiuae/falcon-7b-instruct")
HF_API_KEY = os.getenv("HF_API_KEY", "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")