"""
Configuration and environment variables.
"""
import os

# Load environment variables from .env file (if it exists)
from dotenv import load_dotenv
load_dotenv()

# Database
DB_HOST = os.getenv("DB_HOST", "nv-service-b48efcd4fbe8cf4a875a2ccb70e0e21b")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "nuvolos")
DB_USER = os.getenv("DB_USER", "nuvolos")
DB_PASSWORD = os.getenv("DB_PASSWORD", "nuvolos")

# Server
BACKEND_PORT = int(os.getenv("BACKEND_PORT", "8500"))
# BACKEND_HOST: address for server binding (0.0.0.0 = all interfaces)
BACKEND_HOST = os.getenv("BACKEND_HOST", "0.0.0.0")
# BACKEND_URL: address for client connections (what the frontend uses to call the backend)
BACKEND_URL = os.getenv("BACKEND_URL", "localhost")

# Retrieval
EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", "768"))
DEFAULT_TOP_K = int(os.getenv("DEFAULT_TOP_K", "10"))
MAX_TOP_K = int(os.getenv("MAX_TOP_K", "100"))

# LLM / Generation
DEFAULT_FORMAT = "markdown"  # "markdown" | "text"
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "huggingface")

# Hardcoding Falcon-7b-instruct and your API key as direct fallbacks
HF_MODEL = os.getenv("HF_MODEL", "Qwen/Qwen2.5-1.5B-Instructt")
HF_API_KEY = os.getenv("HF_API_KEY", "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") # attention: do not hardcode API keys in production code! Use environment variables or secret management.
HF_HOME = os.getenv("HF_HOME", "/files/.hf_cache")