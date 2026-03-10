"""Embedding pipeline using nomic-embed-text-v1.5."""

import logging
import numpy as np

logger = logging.getLogger(__name__)

_model = None


def get_model():
    """Lazy-load the embedding model."""
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        logger.info("Loading nomic-embed-text-v1.5")
        _model = SentenceTransformer("nomic-ai/nomic-embed-text-v1.5", trust_remote_code=True)
    return _model


def embed_texts(texts: list[str], prefix: str = "search_document: ") -> list[list[float]]:
    """Embed a batch of texts.

    Args:
        texts: List of text strings to embed
        prefix: Nomic prefix — "search_document: " for indexing, "search_query: " for queries

    Returns:
        List of 384-dim embedding vectors
    """
    model = get_model()
    prefixed = [f"{prefix}{t}" for t in texts]
    embeddings = model.encode(prefixed, normalize_embeddings=True, show_progress_bar=False)
    return embeddings.tolist()


def embed_query(query: str) -> list[float]:
    """Embed a search query."""
    return embed_texts([query], prefix="search_query: ")[0]
