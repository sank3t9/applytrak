"""Backfill description_embedding for all postings missing it.

Run:
    python scripts/embed_pending.py
"""

import logging
import sys

from applytrak.pipeline import run_embed

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


def main() -> int:
    result = run_embed()
    print(f"[DONE] embedded={result.embedded} batches={result.batches} failed={result.failed}")
    return 0 if result.failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
