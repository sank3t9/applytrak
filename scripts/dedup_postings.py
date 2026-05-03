"""Mark duplicate postings via cosine similarity on description_embedding.

Run:
    python scripts/dedup_postings.py
"""

import logging
import sys

from applytrak.pipeline import run_dedup

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


def main() -> int:
    result = run_dedup()
    print(
        f"[DONE] threshold={result.threshold:.2f} "
        f"canonicals_kept={result.canonicals_kept} "
        f"marked_as_duplicate={result.marked_as_duplicate} "
        f"already_resolved={result.already_resolved}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
