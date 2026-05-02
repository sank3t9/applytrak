"""End-to-end Phase 1 demo: find latest 'Who is hiring?', fetch one comment, persist it.

Idempotent: running multiple times won't create duplicates.

Run:
    python scripts/save_one.py
"""

import logging
import sys

import httpx

from applytrak.db import session_scope
from applytrak.services.raw_postings import save_raw_posting
from applytrak.sources.hn import (
    fetch_comment,
    get_latest_who_is_hiring_thread_id,
    get_top_level_comment_ids,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


def main() -> int:
    with httpx.Client(timeout=10.0) as client:
        thread_id = get_latest_who_is_hiring_thread_id(client)
        if thread_id is None:
            print("[FAIL] No 'Who is hiring?' thread found", file=sys.stderr)
            return 1

        comment_ids = get_top_level_comment_ids(client, thread_id)
        if not comment_ids:
            print("[FAIL] thread has no comments", file=sys.stderr)
            return 1

        posting = None
        for cid in comment_ids[:10]:
            posting = fetch_comment(client, cid)
            if posting:
                break
        if posting is None:
            print("[FAIL] none of the first 10 comments were fetchable", file=sys.stderr)
            return 1

    with session_scope() as session:
        row, created = save_raw_posting(session, posting)
        verb = "inserted" if created else "already had"
        print(f"[OK] {verb} raw_posting:")
        print(f"     id          = {row.id}")
        print(f"     source      = {row.source}")
        print(f"     source_id   = {row.source_id}")
        print(f"     url         = {row.url}")
        print(f"     raw_text    = {len(row.raw_text)} chars")

    return 0


if __name__ == "__main__":
    sys.exit(main())
