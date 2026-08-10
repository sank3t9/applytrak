"""Parse all unparsed raw_postings via Claude Haiku.

Run:
    python scripts/parse_pending.py
"""

import logging
import sys

from applytrak.pipeline import run_parse

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


def main() -> int:
    result = run_parse()
    print(f"[DONE] inserted={result.inserted} skipped={result.skipped} failed={result.failed}")
    return 0 if result.failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
