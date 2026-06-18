"""
Embedding generation module using remote model server.

This module uses the local model server (running on Mac) for embeddings.
NO local torch, NO sentence-transformers, NO model loading.

Render backend makes HTTP requests to the local server via ngrok.
"""
import logging
from local_model_client import get_client

logger = logging.getLogger(__name__)

logger.info("✓ Using remote embedding server (NO local model loading)")


def get_embedding(text):
    """
    Generate embedding for input text using remote server.
    
    Args:
        text: Input text string
    
    Returns:
        List of floats representing the embedding vector (384 dimensions)
    """
    if not text or not isinstance(text, str):
        raise ValueError("Input text must be a non-empty string")
    
    # Use remote model client
    client = get_client()
    
    # Get embeddings for single text (returns list of embeddings)
    embeddings = client.embed([text])
    
    # Return first (and only) embedding
    return embeddings[0]


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
    
    # Use remote model client
    client = get_client()
    
    # Get embeddings for batch
    return client.embed(texts)


# NO model loading
# NO SentenceTransformer
# NO torch
# All inference happens on the local server via HTTP
