"""Fetch the latest 'Who is hiring?' thread, grab one comment, print it.

Run:
    python scripts/fetch_one.py
"""

import logging
import sys

import httpx

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
        print(f"[OK] latest thread id = {thread_id}")

        comment_ids = get_top_level_comment_ids(client, thread_id)
        print(f"[OK] thread has {len(comment_ids)} top-level comments")

        if not comment_ids:
            print("[FAIL] thread has no comments", file=sys.stderr)
            return 1

        # Walk until we find a non-deleted comment with text
        posting = None
        for cid in comment_ids[:10]:
            posting = fetch_comment(client, cid)
            if posting:
                break
        if posting is None:
            print("[FAIL] none of the first 10 comments were fetchable", file=sys.stderr)
            return 1

        print("\n--- FetchedPosting ---")
        print(f"source:    {posting.source}")
        print(f"source_id: {posting.source_id}")
        print(f"url:       {posting.url}")
        print(f"raw_text:  ({len(posting.raw_text)} chars)")
        print("---")
        preview = posting.raw_text[:600]
        print(preview + ("...\n[truncated]" if len(posting.raw_text) > 600 else ""))
        print("---")

    return 0


if __name__ == "__main__":
    sys.exit(main())
