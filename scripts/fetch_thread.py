"""Fetch top-N comments from latest 'Who is hiring?' thread → raw_postings.

Usage:
    python scripts/fetch_thread.py        # default limit (30)
    python scripts/fetch_thread.py 100    # explicit limit
"""

import logging
import sys

from applytrak.pipeline import DEFAULT_FETCH_LIMIT, run_fetch

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


def main(limit: int) -> int:
    result = run_fetch(limit=limit)
    print(
        f"[DONE] thread_id={result.thread_id} "
        f"inserted={result.inserted} skipped={result.skipped} "
        f"empty/deleted={result.empty_or_deleted} failed={result.failed}"
    )
    return 0 if result.failed == 0 else 1


if __name__ == "__main__":
    limit_arg = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_FETCH_LIMIT
    sys.exit(main(limit_arg))
