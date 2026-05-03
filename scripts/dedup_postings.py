"""Mark duplicate postings via cosine similarity on description_embedding.

Algorithm:
  Process postings in chronological order. For each, look for an *earlier
  canonical* (canonical_id IS NULL, parsed_at < self) with similarity above
  DEDUPE_SIMILARITY_THRESHOLD. If found, mark this posting as a duplicate
  pointing to that canonical. Otherwise, this posting becomes a new canonical.

Idempotent: re-runs only re-evaluate postings whose canonical_id is still NULL,
but since we never *un*-mark a duplicate, repeated runs converge.

Run:
    python scripts/dedup_postings.py
"""

import logging
import sys

from sqlalchemy import select

from applytrak.config import settings
from applytrak.db import session_scope
from applytrak.models import Posting

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

THRESHOLD = settings.dedupe_similarity_threshold


def main() -> int:
    with session_scope() as session:
        # Process all postings (with embeddings) in chronological order.
        all_postings = list(
            session.scalars(
                select(Posting)
                .where(Posting.description_embedding.is_not(None))
                .order_by(Posting.parsed_at)
            )
        )

        if not all_postings:
            print("[OK] No postings with embeddings.")
            return 0

        print(f"[START] Dedup over {len(all_postings)} postings (threshold={THRESHOLD:.2f})\n")

        canonicals_kept = 0
        marked_duplicate = 0
        already_resolved = 0

        for posting in all_postings:
            if posting.canonical_id is not None:
                already_resolved += 1
                continue

            # Find the most-similar earlier canonical.
            distance_expr = Posting.description_embedding.cosine_distance(
                posting.description_embedding
            )
            row = session.execute(
                select(
                    Posting.id,
                    Posting.company,
                    Posting.title,
                    distance_expr.label("dist"),
                )
                .where(Posting.description_embedding.is_not(None))
                .where(Posting.canonical_id.is_(None))
                .where(Posting.id != posting.id)
                .where(Posting.parsed_at < posting.parsed_at)
                .order_by(distance_expr)
                .limit(1)
            ).first()

            if row is None:
                canonicals_kept += 1
                continue

            similarity = 1.0 - float(row.dist)

            if similarity >= THRESHOLD:
                posting.canonical_id = row.id
                session.flush()
                marked_duplicate += 1
                print(f"  [DUP] {posting.company} | {posting.title[:50]}")
                print(f"        ↳ canonical: {row.company} | {row.title[:50]}")
                print(f"          similarity={similarity:.3f}\n")
            else:
                canonicals_kept += 1

        print(
            f"[DONE] canonicals_kept={canonicals_kept} "
            f"marked_as_duplicate={marked_duplicate} "
            f"already_resolved={already_resolved}"
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
