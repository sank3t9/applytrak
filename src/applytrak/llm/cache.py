"""LLM parse-result cache.

Backend depends on configuration:
  - REDIS_URL set   → Redis SETEX
  - REDIS_URL empty → parse_cache table in Postgres

Key:    parse:<version>:<provider:model>:<sha256(raw_text)>
Value:  ParsedJD JSON
TTL:    PARSE_CACHE_TTL_DAYS (default 30)

The key embeds the active parse provider+model so switching providers never
serves another model's extraction. Bump CACHE_VERSION when changing the parse
prompt or schema in a way that invalidates old extractions.
"""

import hashlib
import logging
from datetime import UTC, datetime, timedelta

from applytrak.config import settings
from applytrak.schemas import ParsedJD

logger = logging.getLogger(__name__)

CACHE_VERSION = "v2"


def _parse_model_tag() -> str:
    if settings.llm_provider == "gemini":
        return f"gemini:{settings.gemini_model_parse}"
    return f"anthropic:{settings.anthropic_model_parse}"


def _cache_key(raw_text: str) -> str:
    digest = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()
    return f"parse:{CACHE_VERSION}:{_parse_model_tag()}:{digest}"


def parse_cache_get(raw_text: str) -> ParsedJD | None:
    """Return the cached ParsedJD for this text, or None on miss / corrupt entry."""
    key = _cache_key(raw_text)
    cached_json = _redis_get(key) if settings.redis_url else _pg_get(key)
    if cached_json is None:
        return None
    try:
        return ParsedJD.model_validate_json(cached_json)
    except Exception as e:
        logger.warning("Cached parse %s failed validation, deleting: %s", key, e)
        if settings.redis_url:
            _redis_delete(key)
        else:
            _pg_delete(key)
        return None


def parse_cache_set(raw_text: str, parsed: ParsedJD) -> None:
    """Store a ParsedJD under the text's hash."""
    key = _cache_key(raw_text)
    ttl_seconds = settings.parse_cache_ttl_days * 24 * 60 * 60
    value = parsed.model_dump_json()
    if settings.redis_url:
        _redis_set(key, value, ttl_seconds)
    else:
        _pg_set(key, value, ttl_seconds)


# ---------------------------------------------------------------------------
# Redis backend
# ---------------------------------------------------------------------------


def _redis_get(key: str) -> str | None:
    from applytrak.redis_client import get_redis

    return get_redis().get(key)


def _redis_set(key: str, value: str, ttl_seconds: int) -> None:
    from applytrak.redis_client import get_redis

    get_redis().setex(key, ttl_seconds, value)


def _redis_delete(key: str) -> None:
    from applytrak.redis_client import get_redis

    get_redis().delete(key)


# ---------------------------------------------------------------------------
# Postgres backend
# ---------------------------------------------------------------------------


def _pg_get(key: str) -> str | None:
    from applytrak.db import session_scope
    from applytrak.models import ParseCache

    with session_scope() as session:
        row = session.get(ParseCache, key)
        if row is None:
            return None
        if row.expires_at <= datetime.now(UTC):
            session.delete(row)
            return None
        return row.value


def _pg_set(key: str, value: str, ttl_seconds: int) -> None:
    from applytrak.db import session_scope
    from applytrak.models import ParseCache

    expires_at = datetime.now(UTC) + timedelta(seconds=ttl_seconds)
    with session_scope() as session:
        row = session.get(ParseCache, key)
        if row is None:
            session.add(ParseCache(cache_key=key, value=value, expires_at=expires_at))
        else:
            row.value = value
            row.expires_at = expires_at


def _pg_delete(key: str) -> None:
    from applytrak.db import session_scope
    from applytrak.models import ParseCache

    with session_scope() as session:
        row = session.get(ParseCache, key)
        if row is not None:
            session.delete(row)
