"""Fetch top-N comments from the latest 'Who is hiring?' thread → raw_postings.

Idempotent: comments already in the DB are skipped (UNIQUE constraint on
source + source_id).

Usage:
    python scripts/fetch_thread.py        # default limit (30)
    python scripts/fetch_thread.py 100    # explicit limit
"""

import logging
import sys
import time

import httpx

from applytrak.db import session_scope
from applytrak.services.raw_postings import save_raw_posting
from applytrak.sources.hn import (
    fetch_comment,
    get_latest_who_is_hiring_thread_id,
    get_top_level_comment_ids,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

DEFAULT_LIMIT = 30
SLEEP_BETWEEN_FETCHES_S = 0.1  # be polite to HN's API


def main(limit: int = DEFAULT_LIMIT) -> int:
    with httpx.Client(timeout=10.0) as client:
        thread_id = get_latest_who_is_hiring_thread_id(client)
        if thread_id is None:
            print("[FAIL] No 'Who is hiring?' thread found", file=sys.stderr)
            return 1

        all_comment_ids = get_top_level_comment_ids(client, thread_id)
        targets = all_comment_ids[:limit]
        print(
            f"[START] Fetching top {len(targets)} of {len(all_comment_ids)} "
            f"comments from thread {thread_id}\n"
        )

        inserted = 0
        skipped = 0
        empty = 0
        failed = 0

        for i, cid in enumerate(targets, start=1):
            try:
                posting = fetch_comment(client, cid)
            except Exception as e:
                print(f"  [FAIL] cid={cid}: {type(e).__name__}: {e}")
                failed += 1
                continue

            if posting is None:
                empty += 1
                continue

            with session_scope() as session:
                _, created = save_raw_posting(session, posting)
                if created:
                    inserted += 1
                else:
                    skipped += 1

            if i % 10 == 0:
                print(f"  ... processed {i}/{len(targets)}")

            time.sleep(SLEEP_BETWEEN_FETCHES_S)

    print(
        f"\n[DONE] inserted={inserted} skipped={skipped} "
        f"empty/deleted={empty} failed={failed}"
    )
    return 0


if __name__ == "__main__":
    limit_arg = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_LIMIT
    sys.exit(main(limit_arg))
