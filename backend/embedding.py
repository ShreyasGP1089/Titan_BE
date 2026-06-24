"""
Embedding generation module using local sentence-transformers.

This module generates embeddings locally in the backend using sentence-transformers.
NO HTTP calls to model server for embeddings.

The model server (local_model_server.py) should ONLY handle intent parsing.
"""
import logging
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

# Model configuration
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
EMBEDDING_DIMENSION = 384

# Load model once at module level
logger.info(f"Loading embedding model: {EMBEDDING_MODEL}")
try:
    _model = SentenceTransformer(EMBEDDING_MODEL)
    logger.info(f"✓ Embedding model loaded successfully (dimension: {EMBEDDING_DIMENSION})")
except Exception as e:
    logger.error(f"❌ Failed to load embedding model: {e}")
    _model = None


def get_embedding(text):
    """
    Generate embedding for input text using local sentence-transformers.
    
    Args:
        text: Input text string
    
    Returns:
        List of floats representing the embedding vector (384 dimensions)
    
    Raises:
        ValueError: If text is empty or model not loaded
    """
    if not text or not isinstance(text, str):
        raise ValueError("Input text must be a non-empty string")
    
    if _model is None:
        raise RuntimeError("Embedding model not loaded")
    
    # Generate embedding with normalization
    embedding = _model.encode(
        text,
        normalize_embeddings=True
    )
    
    # Convert numpy array to list
    return embedding.tolist()


def get_embeddings_batch(texts):
    """
    Generate embeddings for multiple texts using local sentence-transformers.
    
    Args:
        texts: List of text strings
    
    Returns:
        List of embedding vectors
    
    Raises:
        ValueError: If texts is empty or model not loaded
    """
    if not texts or not isinstance(texts, list):
        raise ValueError("Input must be a non-empty list of strings")
    
    if _model is None:
        raise RuntimeError("Embedding model not loaded")
    
    # Generate embeddings with normalization (batch processing)
    embeddings = _model.encode(
        texts,
        normalize_embeddings=True,
        batch_size=32
    )
    
    # Convert numpy arrays to lists
    return [emb.tolist() for emb in embeddings]


# NO HTTP calls to /embed endpoint
# NO dependency on local_model_client
# All embedding generation happens locally using sentence-transformers
