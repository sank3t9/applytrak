"""Backfill description_embedding for all postings missing it.

Idempotent: re-runs skip postings that already have an embedding.

Run after parse_pending.py to embed any newly-parsed postings.

Run:
    python scripts/embed_pending.py
"""

import logging
import sys

from sqlalchemy import select

from applytrak.db import session_scope
from applytrak.llm.embeddings import embed_texts
from applytrak.models import Posting, RawPosting

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

BATCH_SIZE = 16


def main() -> int:
    # Stage 1: snapshot the work-list, then close the session.
    with session_scope() as session:
        stmt = (
            select(Posting.id, RawPosting.raw_text)
            .join(RawPosting, Posting.raw_posting_id == RawPosting.id)
            .where(Posting.description_embedding.is_(None))
            .order_by(Posting.parsed_at)
        )
        rows: list[tuple] = list(session.execute(stmt).all())

    if not rows:
        print("[OK] All postings already have embeddings. Nothing to do.")
        return 0

    print(f"[START] Embedding {len(rows)} postings in batches of {BATCH_SIZE}...\n")

    embedded = 0
    failed = 0
    n_batches = (len(rows) + BATCH_SIZE - 1) // BATCH_SIZE

    for batch_idx, start in enumerate(range(0, len(rows), BATCH_SIZE), start=1):
        batch = rows[start : start + BATCH_SIZE]
        ids = [row[0] for row in batch]
        texts = [row[1] for row in batch]

        print(f"[EMBED] batch {batch_idx}/{n_batches} ({len(batch)} postings)")
        try:
            vectors = embed_texts(texts)
        except Exception as e:
            print(f"  [FAIL] {type(e).__name__}: {e}")
            failed += len(batch)
            continue

        # Stage 3: short DB session per batch to write the vectors.
        with session_scope() as session:
            for posting_id, vec in zip(ids, vectors, strict=True):
                p = session.get(Posting, posting_id)
                if p is not None:
                    p.description_embedding = vec
                    embedded += 1

        print(f"  [OK] embedded {len(batch)}\n")

    print(f"[DONE] embedded={embedded} failed={failed}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
