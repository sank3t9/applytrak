"""Smoke test for the parse cache: parse the same text twice, time both calls.

First call should miss (slow, real LLM).
Second call should hit (fast, no LLM).

Run:
    python scripts/cache_smoke.py
"""

import logging
import sys
import time

from sqlalchemy import select

from applytrak.db import session_scope
from applytrak.llm.parse_prompt import parse_jd
from applytrak.models import RawPosting

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


def main() -> int:
    with session_scope() as session:
        raw = session.scalar(select(RawPosting).limit(1))
        if raw is None:
            print("[FAIL] No raw_postings in DB.", file=sys.stderr)
            return 1
        text = raw.raw_text

    print("\n=== Call 1 (expected: cache miss → real LLM call) ===")
    t0 = time.perf_counter()
    parsed1 = parse_jd(text)
    t1 = time.perf_counter()
    print(f"[OK] {parsed1.company} | {parsed1.title}  ({(t1 - t0):.2f}s)")

    print("\n=== Call 2 (expected: cache hit → no LLM call) ===")
    t0 = time.perf_counter()
    parsed2 = parse_jd(text)
    t1 = time.perf_counter()
    print(f"[OK] {parsed2.company} | {parsed2.title}  ({(t1 - t0):.2f}s)")

    same = parsed1.model_dump() == parsed2.model_dump()
    print(f"\nResults identical: {same}")

    return 0 if same else 1


if __name__ == "__main__":
    sys.exit(main())
