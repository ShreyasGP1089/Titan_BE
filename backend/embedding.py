"""
Embedding generation module using remote model server.

This module uses the local model server (running on Mac) for embeddings.
NO local torch, NO sentence-transformers, NO model loading in backend.
"""
import logging
import os
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)

# Configuration
LOCAL_MODEL_URL = os.getenv("LOCAL_MODEL_URL", "http://localhost:8000")
EMBEDDING_DIMENSION = 384

logger.info(f"✓ Using remote embedding server at {LOCAL_MODEL_URL}")


def get_embedding(text):
    """
    Generate embedding for input text using remote server.
    
    Args:
        text: Input text string
    
    Returns:
        List of floats representing the embedding vector
    """
    if not text or not isinstance(text, str):
        raise ValueError("Input text must be a non-empty string")
    
    url = f"{LOCAL_MODEL_URL}/embed"
    try:
        payload = {"texts": [text]}
        response = requests.post(url, json=payload, timeout=30)
        
        if response.status_code != 200:
            logger.error(f"❌ Embed failed with status {response.status_code}: {response.text}")
            raise ValueError(f"Embed failed with status {response.status_code}: {response.text}")
            
        result = response.json()
        if "embeddings" not in result or not result["embeddings"]:
            raise ValueError("Invalid response: 'embeddings' field missing or empty")
            
        return result["embeddings"][0]
        
    except Exception as e:
        logger.error(f"Failed to generate embedding via HTTP: {e}")
        raise


def get_embeddings_batch(texts):
    """
    Generate embeddings for multiple texts using remote server.
    
    Args:
        texts: List of text strings
    
    Returns:
        List of embedding vectors
    """
    if not texts or not isinstance(texts, list):
        raise ValueError("Input must be a non-empty list of strings")
        
    url = f"{LOCAL_MODEL_URL}/embed"
    try:
        payload = {"texts": texts}
        response = requests.post(url, json=payload, timeout=30)
        
        if response.status_code != 200:
            logger.error(f"❌ Embed batch failed with status {response.status_code}: {response.text}")
            raise ValueError(f"Embed batch failed with status {response.status_code}: {response.text}")
            
        result = response.json()
        if "embeddings" not in result:
            raise ValueError("Invalid response: 'embeddings' field missing")
            
        return result["embeddings"]
        
    except Exception as e:
        logger.error(f"Failed to generate batch embeddings via HTTP: {e}")
        raise
