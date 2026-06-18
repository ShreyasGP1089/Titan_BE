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
POSTGRES_DB = os.getenv("POSTGRES_DB", "decathlon")
POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "")

# Embedding Model Configuration
EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"
EMBEDDING_DIMENSION = 384

# LLM Configuration
OLLAMA_MODEL = "qwen3:4b"

# Search Configuration
DEFAULT_SEARCH_LIMIT = 10
MAX_ITERATIONS = 3

# System Prompt
SYSTEM_PROMPT = """You are an AI Shopping Planner for Decathlon products.

You have access to these tools:
1. hybrid_search(query, sport=None, price_limit=None, limit=10) - Search products from database
2. get_categories() - Get available sports and categories
3. compare_products(ids) - Compare specific products by ID

Rules:
- Understand the user's goal and activity requirements
- Identify equipment categories needed for the activity
- Search products using tools multiple times if needed
- If insufficient products are found, refine your search query
- Recommend ONLY products returned by tools
- Never invent products, prices, or specifications
- Prefer highly rated products (rating > 4.0)
- Consider price-to-value ratio
- Explain your recommendations clearly

Response Format (JSON only):
For searching:
{"action": "search", "query": "...", "sport": "...", "price_limit": ...}

For comparing:
{"action": "compare", "ids": ["id1", "id2", ...]}

For answering:
{
  "action": "answer",
  "essentials": ["item1", "item2", ...],
  "optional": ["item3", "item4", ...],
  "recommended_products": [
    {
      "product_id": "...",
      "name": "...",
      "price": ...,
      "rating": ...,
      "reason": "why this product fits"
    }
  ],
  "reasoning": "overall explanation"
}

Always output valid JSON only. No additional text."""
