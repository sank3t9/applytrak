"""Per-key per-minute rate limiter.

Backend depends on configuration:
  - REDIS_URL set   → Redis INCR + EXPIRE on a per-minute key (shared across processes)
  - REDIS_URL empty → in-process sliding window (pipeline runs and serverless
    instances are single-process, so a local window is enough)

Usage:
    with acquire_rate_limit("anthropic", max_per_minute=30):
        client.messages.create(...)
"""

import logging
import threading
import time
from collections import defaultdict, deque
from collections.abc import Iterator
from contextlib import contextmanager

from applytrak.config import settings

logger = logging.getLogger(__name__)


@contextmanager
def acquire_rate_limit(
    key: str,
    *,
    max_per_minute: int,
    max_wait_s: float = 90.0,
) -> Iterator[None]:
    """Block until a slot is available in the per-minute window for this key."""
    if settings.redis_url:
        yield from _acquire_redis(key, max_per_minute=max_per_minute, max_wait_s=max_wait_s)
    else:
        yield from _acquire_local(key, max_per_minute=max_per_minute, max_wait_s=max_wait_s)


def _acquire_redis(key: str, *, max_per_minute: int, max_wait_s: float) -> Iterator[None]:
    from applytrak.redis_client import get_redis

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
            key,
            count,
            max_per_minute,
            seconds_until_next_window,
        )
        time.sleep(seconds_until_next_window)


_local_lock = threading.Lock()
_local_windows: dict[str, deque[float]] = defaultdict(deque)


def _acquire_local(key: str, *, max_per_minute: int, max_wait_s: float) -> Iterator[None]:
    deadline = time.time() + max_wait_s

    while True:
        acquired = False
        wait_s = 0.0
        with _local_lock:
            now = time.time()
            window = _local_windows[key]
            while window and now - window[0] >= 60.0:
                window.popleft()

            if len(window) < max_per_minute:
                window.append(now)
                acquired = True
            else:
                wait_s = 60.0 - (now - window[0]) + 0.1

        if acquired:
            yield
            return

        if time.time() + wait_s > deadline:
            raise TimeoutError(
                f"Rate limit exceeded on {key!r} after waiting {max_wait_s}s "
                f"(window full at {max_per_minute}/min)"
            )

        logger.info(
            "[rate-limit] %s: %d/%d in current window, waiting %.1fs",
            key,
            max_per_minute,
            max_per_minute,
            wait_s,
        )
        time.sleep(wait_s)
