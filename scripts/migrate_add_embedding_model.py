"""One-shot migration: add embedding_model column to postings table.

Records which model produced each description_embedding so run_embed can
re-embed stale rows after an EMBEDDING_PROVIDER switch, and dedup/match can
avoid comparing vectors from different models.

Existing rows are backfilled with the currently configured tag on the
assumption that they were embedded with it (true for single-provider
deployments; if not, set them to NULL to force a re-embed).

Idempotent.

Run:
    python scripts/migrate_add_embedding_model.py
"""

import sys

from sqlalchemy import text

from applytrak.db import engine
from applytrak.llm.embeddings import current_embedding_model


def main() -> int:
    tag = current_embedding_model()

    with engine.begin() as conn:
        conn.execute(
            text("ALTER TABLE postings ADD COLUMN IF NOT EXISTS embedding_model varchar(64);")
        )
        result = conn.execute(
            text(
                """
                UPDATE postings
                SET embedding_model = :tag
                WHERE description_embedding IS NOT NULL
                  AND embedding_model IS NULL;
                """
            ),
            {"tag": tag},
        )

    print("[OK] migration applied: postings.embedding_model column ready")
    print(f"     backfilled {result.rowcount} existing embedded row(s) with {tag!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
