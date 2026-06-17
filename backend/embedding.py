"""
Embedding generation module.
Uses sentence-transformers with BAAI/bge-small-en-v1.5 model.
"""
from sentence_transformers import SentenceTransformer
import logging
from config import EMBEDDING_MODEL

logger = logging.getLogger(__name__)

# Global model instance (loaded once)
_model = None


def load_model():
    """Load the embedding model (singleton pattern)."""
    global _model
    if _model is None:
        logger.info(f"Loading embedding model: {EMBEDDING_MODEL}")
        _model = SentenceTransformer(EMBEDDING_MODEL)
        logger.info("Embedding model loaded successfully")
    return _model


def get_embedding(text):
    """
    Generate embedding for input text.
    
    Args:
        text: Input text string
    
    Returns:
        List of floats representing the embedding vector (384 dimensions)
    """
    if not text or not isinstance(text, str):
        raise ValueError("Input text must be a non-empty string")
    
    model = load_model()
    
    # Generate embedding with normalization
    embedding = model.encode(
        text,
        normalize_embeddings=True,
        show_progress_bar=False
    )
    
    # Convert numpy array to list
    return embedding.tolist()


def get_embeddings_batch(texts):
    """
    Generate embeddings for multiple texts (batch processing).
    
    Args:
        texts: List of text strings
    
    Returns:
        List of embedding vectors
    """
    if not texts or not isinstance(texts, list):
        raise ValueError("Input must be a non-empty list of strings")
    
    model = load_model()
    
    embeddings = model.encode(
        texts,
        normalize_embeddings=True,
        show_progress_bar=False,
        batch_size=32
    )
    
    return [emb.tolist() for emb in embeddings]
