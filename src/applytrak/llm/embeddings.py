"""Embeddings client for the configured provider (Voyage or Gemini).

Public API:
    embed_text(text)             -> list[float]            # one embedding
    embed_texts(texts)           -> list[list[float]]      # batch
    current_embedding_model()    -> str                    # provenance tag

All providers are configured to return 1024-dim vectors so the postings.
description_embedding column type never changes. Vectors from different
providers/models are NOT comparable — every row records which model produced
it (see current_embedding_model) and run_embed re-embeds rows whose tag no
longer matches the active configuration.

`input_type` distinguishes the two sides of a similarity search: "document"
for stored content (job postings), "query" for the text you search with
(a visitor's resume).
"""

from typing import Literal

from applytrak.config import settings

InputType = Literal["document", "query"]

EMBEDDING_DIM = 1024

_voyage_client = None


def current_embedding_model() -> str:
    """Provenance tag stored alongside each vector: '<provider>:<model>'."""
    if settings.embedding_provider == "gemini":
        return f"gemini:{settings.gemini_embedding_model}"
    return f"voyage:{settings.embedding_model}"


def embed_text(text: str, *, input_type: InputType = "document") -> list[float]:
    """Embed one string. Returns a 1024-dim vector."""
    return embed_texts([text], input_type=input_type)[0]


def embed_texts(texts: list[str], *, input_type: InputType = "document") -> list[list[float]]:
    """Embed multiple strings in one API call. Use for batches."""
    if settings.embedding_provider == "gemini":
        return _embed_gemini(texts, input_type=input_type)
    return _embed_voyage(texts, input_type=input_type)


# ---------------------------------------------------------------------------
# Voyage
# ---------------------------------------------------------------------------


def _get_voyage_client():
    """Lazy-init the Voyage client so importing this module doesn't require a key."""
    global _voyage_client
    if _voyage_client is None:
        if not settings.voyage_api_key:
            raise RuntimeError(
                "VOYAGE_API_KEY is not set in .env. Sign up at https://www.voyageai.com/ "
                "or switch to EMBEDDING_PROVIDER=gemini."
            )
        import voyageai

        _voyage_client = voyageai.Client(api_key=settings.voyage_api_key)
    return _voyage_client


def _embed_voyage(texts: list[str], *, input_type: InputType) -> list[list[float]]:
    result = _get_voyage_client().embed(
        texts,
        model=settings.embedding_model,
        input_type=input_type,
    )
    return result.embeddings


# ---------------------------------------------------------------------------
# Gemini
# ---------------------------------------------------------------------------

_GEMINI_TASK_TYPES: dict[InputType, str] = {
    "document": "RETRIEVAL_DOCUMENT",
    "query": "RETRIEVAL_QUERY",
}


def _embed_gemini(texts: list[str], *, input_type: InputType) -> list[list[float]]:
    from google.genai import types as genai_types

    from applytrak.llm.providers import get_gemini_client

    response = get_gemini_client().models.embed_content(
        model=settings.gemini_embedding_model,
        contents=texts,
        config=genai_types.EmbedContentConfig(
            task_type=_GEMINI_TASK_TYPES[input_type],
            output_dimensionality=EMBEDDING_DIM,
        ),
    )
    # Only the full 3072-dim output is pre-normalized; truncated dimensions must
    # be re-normalized before cosine comparisons.
    return [_l2_normalize(e.values) for e in response.embeddings]


def _l2_normalize(vector: list[float]) -> list[float]:
    magnitude = sum(v * v for v in vector) ** 0.5
    if magnitude == 0:
        return vector
    return [v / magnitude for v in vector]
