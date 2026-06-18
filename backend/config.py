"""
Configuration module for the conversational commerce backend.
Manages environment variables and application settings.
"""
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Database Configuration
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
POSTGRES_DB = os.getenv("POSTGRES_DB", "decathlon_rag")
POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "")

# HuggingFace Model Configuration
HF_BASE_MODEL_NAME = os.getenv("HF_BASE_MODEL_NAME", "Qwen/Qwen2.5-1.5B-Instruct")
HF_ADAPTER_PATH = os.getenv("HF_ADAPTER_PATH", "../training/outputs/qwen25_1_5b_lora_hf")

# Embedding Model Configuration
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
EMBEDDING_DIMENSION = 384

# Search Configuration
DEFAULT_SEARCH_LIMIT = 10
MAX_ITERATIONS = 3

# API Configuration
API_KEY = os.getenv("API_KEY", "decathlon_smart_search_2024_secure_key_abc123xyz")
PRELOAD_MODEL = os.getenv("PRELOAD_MODEL", "false").lower() == "true"

# System Prompt for Query Parsing
SYSTEM_PROMPT = """You are a JSON parser for shopping queries. You MUST respond with ONLY valid JSON, no other text.

Output format:
{
  "intent": "search" or "task",
  "search_request": {...} (if intent is "search"),
  "search_requests": [{...}, {...}] (if intent is "task")
}

Examples:
Query: "running shoes under 5000"
{"intent": "search", "search_request": {"sport": "Running", "category": "Running Shoes", "keywords": ["shoes"], "price_limit": 5000}}

Query: "I want to start playing football"
{"intent": "task", "search_requests": [{"sport": "Football", "category": "Football", "keywords": []}, {"sport": "Football", "category": "Football Shoes", "keywords": ["shoes"]}]}

Now parse this query:"""
