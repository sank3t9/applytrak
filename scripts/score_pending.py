"""Score all unscored canonical postings via Claude Sonnet.

Run:
    python scripts/score_pending.py
"""

import logging
import sys

from applytrak.pipeline import run_score

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


def main() -> int:
    result = run_score()
    print(
        f"[DONE] inserted={result.inserted} "
        f"skipped={result.skipped} failed={result.failed}"
    )
    return 0 if result.failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
