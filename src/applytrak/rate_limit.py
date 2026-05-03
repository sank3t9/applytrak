"""Per-key per-minute rate limiter backed by Redis.

Pattern: token-bucket-ish using Redis INCR + EXPIRE on a per-minute key.
When the bucket is full, blocks until the next minute window or until
max_wait_s, whichever comes first.

Usage:
    with acquire_rate_limit("anthropic", max_per_minute=30):
        client.messages.create(...)
"""

import logging
import time
from collections.abc import Iterator
from contextlib import contextmanager

from applytrak.redis_client import get_redis

logger = logging.getLogger(__name__)


@contextmanager
def acquire_rate_limit(
    key: str,
    *,
    max_per_minute: int,
    max_wait_s: float = 90.0,
) -> Iterator[None]:
    """Block until a slot is available in the per-minute window for this key."""
    redis = get_redis()
    deadline = time.time() + max_wait_s

    while True:
        now = time.time()
        window_id = int(now // 60)
        bucket_key = f"ratelimit:{key}:{window_id}"

        count = redis.incr(bucket_key)
        if count == 1:
            redis.expire(bucket_key, 70)

        if count <= max_per_minute:
            yield
            return

        seconds_until_next_window = 60 - (now - window_id * 60) + 0.1
        if now + seconds_until_next_window > deadline:
            raise TimeoutError(
                f"Rate limit exceeded on {key!r} after waiting {max_wait_s}s "
                f"(current window count={count}/{max_per_minute})"
            )

        logger.info(
            "[rate-limit] %s: %d/%d in current window, waiting %.1fs for next",
            key, count, max_per_minute, seconds_until_next_window,
        )
        time.sleep(seconds_until_next_window)
