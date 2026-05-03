"""Redis client singleton.

Used by the cache and rate limiter modules. Lazy-init so importing this
module doesn't connect to Redis (helpful in tests, scripts that don't
need it).
"""

import redis

from applytrak.config import settings

_client: redis.Redis | None = None


def get_redis() -> redis.Redis:
    global _client
    if _client is None:
        _client = redis.Redis.from_url(settings.redis_url, decode_responses=True)
    return _client
