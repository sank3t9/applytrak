"""One-shot migration: add description_embedding column to postings table.

Idempotent (uses IF NOT EXISTS clauses).

In a real production codebase we would use Alembic instead of these one-shot
scripts. Documented as a V1 simplification in the README.

Run:
    python scripts/migrate_add_embeddings.py
"""

import sys

from sqlalchemy import text

from applytrak.db import engine


def main() -> int:
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
        conn.execute(
            text(
                "ALTER TABLE postings "
                "ADD COLUMN IF NOT EXISTS description_embedding vector(1024);"
            )
        )

    print("[OK] migration applied: postings.description_embedding column ready")
    return 0


if __name__ == "__main__":
    sys.exit(main())
