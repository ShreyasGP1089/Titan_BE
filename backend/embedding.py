"""
Embedding generation module with local/remote fallback.

Uses sentence-transformers locally when available.
Otherwise falls back to the remote model server (/embed endpoint).
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
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
EMBEDDING_DIMENSION = 384

# Try loading the local embedding model
try:
    from sentence_transformers import SentenceTransformer

    HAS_SENTENCE_TRANSFORMERS = True

    logger.info(f"Loading embedding model locally: {EMBEDDING_MODEL}")

    _model = SentenceTransformer(EMBEDDING_MODEL)

    logger.info(
        f"✓ Local embedding model loaded successfully "
        f"(dimension: {EMBEDDING_DIMENSION})"
    )

except ImportError:
    HAS_SENTENCE_TRANSFORMERS = False
    _model = None
    logger.info(
        "sentence_transformers not available. "
        "Using remote embedding server."
    )

except Exception as e:
    HAS_SENTENCE_TRANSFORMERS = False
    _model = None
    logger.warning(
        f"Failed to load local embedding model: {e}. "
        "Falling back to remote embedding server."
    )


def get_embedding(text):
    """
    Generate an embedding for a single text.

    Uses the local SentenceTransformer if available.
    Otherwise calls the remote model server.
    """

    if not text or not isinstance(text, str):
        raise ValueError("Input text must be a non-empty string")

    # Local embedding
    if HAS_SENTENCE_TRANSFORMERS and _model is not None:
        embedding = _model.encode(
            text,
            normalize_embeddings=True,
        )
        return embedding.tolist()

    # Remote embedding
    url = f"{LOCAL_MODEL_URL}/embed"

    logger.info(f"Generating embedding remotely via HTTP: {url}")

    try:
        response = requests.post(
            url,
            json={"texts": [text]},
            timeout=30,
        )

        response.raise_for_status()

        result = response.json()

        if "embeddings" not in result or not result["embeddings"]:
            raise RuntimeError("Invalid embedding response from model server.")

        return result["embeddings"][0]

    except Exception as e:
        logger.error(f"Remote embedding generation failed: {e}")
        raise RuntimeError(
            f"Remote embedding generation failed: {e}"
        ) from e


def get_embeddings_batch(texts):
    """
    Generate embeddings for multiple texts.

    Uses the local SentenceTransformer if available.
    Otherwise calls the remote model server.
    """

    if not texts or not isinstance(texts, list):
        raise ValueError("Input must be a non-empty list of strings")

    # Local embedding
    if HAS_SENTENCE_TRANSFORMERS and _model is not None:
        embeddings = _model.encode(
            texts,
            normalize_embeddings=True,
            batch_size=32,
        )

        return [emb.tolist() for emb in embeddings]

    # Remote embedding
    url = f"{LOCAL_MODEL_URL}/embed"

    logger.info(f"Generating batch embeddings remotely via HTTP: {url}")

    try:
        response = requests.post(
            url,
            json={"texts": texts},
            timeout=30,
        )

        response.raise_for_status()

        result = response.json()

        if "embeddings" not in result:
            raise RuntimeError("Invalid embedding response from model server.")

        return result["embeddings"]

    except Exception as e:
        logger.error(f"Remote batch embedding generation failed: {e}")
        raise RuntimeError(
            f"Remote batch embedding generation failed: {e}"
        ) from e