"""Voyage AI embeddings client.

Public API:
    embed_text(text)        -> list[float]            # one embedding
    embed_texts(texts)      -> list[list[float]]      # batch
"""

import voyageai

from applytrak.config import settings

_client: voyageai.Client | None = None

# Voyage's recommended input_type: 'document' for content to be searched,
# 'query' for the search query itself. We embed JD descriptions as documents.
DEFAULT_INPUT_TYPE = "document"


def _get_client() -> voyageai.Client:
    """Lazy-init the Voyage client so importing this module doesn't require an API key."""
    global _client
    if _client is None:
        if not settings.voyage_api_key:
            raise RuntimeError(
                "VOYAGE_API_KEY is not set in .env. Sign up at https://www.voyageai.com/"
            )
        _client = voyageai.Client(api_key=settings.voyage_api_key)
    return _client


def embed_text(text: str, *, input_type: str = DEFAULT_INPUT_TYPE) -> list[float]:
    """Embed one string. Returns a 1024-dim vector for voyage-3."""
    client = _get_client()
    result = client.embed([text], model=settings.embedding_model, input_type=input_type)
    return result.embeddings[0]


def embed_texts(
    texts: list[str], *, input_type: str = DEFAULT_INPUT_TYPE
) -> list[list[float]]:
    """Embed multiple strings in one API call. Use for batches (faster, fewer requests)."""
    client = _get_client()
    result = client.embed(texts, model=settings.embedding_model, input_type=input_type)
    return result.embeddings
