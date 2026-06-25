"""
Embedding generation module with local/remote fallback.

Generates embeddings locally using sentence-transformers if available.
Otherwise, falls back to remote HTTP calls to the model server (local_model_server.py).
"""
import logging
import os

logger = logging.getLogger(__name__)

# Model configuration
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
EMBEDDING_DIMENSION = 384
LOCAL_MODEL_URL = os.getenv('LOCAL_MODEL_URL', 'http://localhost:8000')

try:
    from sentence_transformers import SentenceTransformer
    HAS_SENTENCE_TRANSFORMERS = True
    logger.info(f"Loading embedding model locally: {EMBEDDING_MODEL}")
    _model = SentenceTransformer(EMBEDDING_MODEL)
    logger.info(f"✓ Local embedding model loaded successfully (dimension: {EMBEDDING_DIMENSION})")
except ImportError:
    HAS_SENTENCE_TRANSFORMERS = False
    _model = None
    logger.info("sentence_transformers package not found. Using remote HTTP embedding generation.")
except Exception as e:
    HAS_SENTENCE_TRANSFORMERS = False
    _model = None
    logger.warning(f"⚠️ Failed to load local embedding model: {e}. Falling back to remote HTTP embedding generation.")


def get_embedding(text):
    """
    Generate embedding for input text.
    Uses local model if available, otherwise calls remote HTTP endpoint.
    
    Args:
        text: Input text string
    
    Returns:
        List of floats representing the embedding vector (384 dimensions)
    """
    if not text or not isinstance(text, str):
        raise ValueError("Input text must be a non-empty string")
    
    if HAS_SENTENCE_TRANSFORMERS and _model is not None:
        # Local execution
        embedding = _model.encode(
            text,
            normalize_embeddings=True
        )
        return embedding.tolist()
    else:
        # Remote HTTP execution
        import requests
        url = f"{LOCAL_MODEL_URL}/embed"
        logger.info(f"Generating embedding remotely via HTTP: {url}")
        try:
            response = requests.post(
                url,
                json={"texts": [text]},
                timeout=15
            )
            if response.status_code != 200:
                raise RuntimeError(f"Model server returned status code {response.status_code}: {response.text}")
            result = response.json()
            return result["embeddings"][0]
        except Exception as e:
            logger.error(f"Remote embedding generation failed: {e}")
            raise RuntimeError(f"Remote embedding generation failed: {e}") from e


def get_embeddings_batch(texts):
    """
    Generate embeddings for a batch of texts.
    Uses local model if available, otherwise calls remote HTTP endpoint.
    
    Args:
        texts: List of text strings
    
    Returns:
        List of embedding vectors
    """
    if not texts or not isinstance(texts, list):
        raise ValueError("Input must be a non-empty list of strings")
    
    if HAS_SENTENCE_TRANSFORMERS and _model is not None:
        # Local execution
        embeddings = _model.encode(
            texts,
            normalize_embeddings=True,
            batch_size=32
        )
        return [emb.tolist() for emb in embeddings]
    else:
        # Remote HTTP execution
        import requests
        url = f"{LOCAL_MODEL_URL}/embed"
        logger.info(f"Generating batch embeddings remotely via HTTP: {url}")
        try:
            response = requests.post(
                url,
                json={"texts": texts},
                timeout=30
            )
            if response.status_code != 200:
                raise RuntimeError(f"Model server returned status code {response.status_code}: {response.text}")
            result = response.json()
            return result["embeddings"]
        except Exception as e:
            logger.error(f"Remote batch embedding generation failed: {e}")
            raise RuntimeError(f"Remote batch embedding generation failed: {e}") from e
