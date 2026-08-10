"""One-shot migration: add posted_at column to raw_postings table.

Records when the source published a posting, as distinct from when we ingested
it. Rows fetched before this existed keep NULL; queries fall back to fetched_at.

Idempotent.

Run:
    python scripts/migrate_add_posted_at.py
"""

import sys

from sqlalchemy import text

from applytrak.db import engine


def main() -> int:
    with engine.begin() as conn:
        conn.execute(
            text("ALTER TABLE raw_postings ADD COLUMN IF NOT EXISTS posted_at timestamptz;")
        )
        missing = conn.execute(
            text("SELECT count(*) FROM raw_postings WHERE posted_at IS NULL;")
        ).scalar_one()

    print("[OK] migration applied: raw_postings.posted_at column ready")
    if missing:
        print(f"     {missing} existing row(s) have no posted_at (queries fall back to fetched_at)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
