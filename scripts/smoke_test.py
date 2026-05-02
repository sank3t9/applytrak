"""Smoke test: verifies Postgres (+ pgvector) and Redis are reachable.

Run from the repo root with the venv active:
    python scripts/smoke_test.py
"""

import sys

import psycopg
import redis

from applytrak.config import settings


def check_postgres() -> None:
    print("[postgres] connecting...")
    with psycopg.connect(settings.database_url) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT version();")
            version = cur.fetchone()[0]
            print(f"[postgres] connected: {version.split(',')[0]}")

            cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
            conn.commit()

            cur.execute("SELECT extversion FROM pg_extension WHERE extname = 'vector';")
            ext_version = cur.fetchone()[0]
            print(f"[postgres] pgvector extension enabled (v{ext_version})")


def check_redis() -> None:
    print("[redis] connecting...")
    r = redis.Redis.from_url(settings.redis_url, decode_responses=True)

    pong = r.ping()
    print(f"[redis] ping -> {pong}")

    r.set("smoke:test", "hello")
    value = r.get("smoke:test")
    print(f"[redis] roundtrip: set('smoke:test', 'hello') -> get -> {value!r}")
    r.delete("smoke:test")


def main() -> int:
    try:
        check_postgres()
        check_redis()
    except Exception as e:
        print(f"\n[FAIL] {type(e).__name__}: {e}", file=sys.stderr)
        return 1

    print("\n[OK] all systems go.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
