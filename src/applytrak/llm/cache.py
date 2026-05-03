"""LLM parse-result cache backed by Redis.

Key:    parse:v1:<sha256(raw_text)>
Value:  ParsedJD JSON
TTL:    PARSE_CACHE_TTL_DAYS (default 30)

Bump the version prefix when changing the parse prompt or schema in a way
that invalidates old extractions.
"""

import hashlib
import logging

from applytrak.config import settings
from applytrak.redis_client import get_redis
from applytrak.schemas import ParsedJD

logger = logging.getLogger(__name__)

CACHE_VERSION = "v1"
KEY_PREFIX = f"parse:{CACHE_VERSION}:"


def _cache_key(raw_text: str) -> str:
    digest = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()
    return KEY_PREFIX + digest


def parse_cache_get(raw_text: str) -> ParsedJD | None:
    """Return the cached ParsedJD for this text, or None on miss / corrupt entry."""
    key = _cache_key(raw_text)
    cached_json = get_redis().get(key)
    if cached_json is None:
        return None
    try:
        return ParsedJD.model_validate_json(cached_json)
    except Exception as e:
        logger.warning("Cached parse %s failed validation, deleting: %s", key, e)
        get_redis().delete(key)
        return None


def parse_cache_set(raw_text: str, parsed: ParsedJD) -> None:
    """Store a ParsedJD under the text's hash."""
    key = _cache_key(raw_text)
    ttl_seconds = settings.parse_cache_ttl_days * 24 * 60 * 60
    get_redis().setex(key, ttl_seconds, parsed.model_dump_json())
