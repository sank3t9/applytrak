"""One-shot migration: add canonical_id column to postings table.

Idempotent.

Run:
    python scripts/migrate_add_canonical_id.py
"""

import sys

from sqlalchemy import text

from applytrak.db import engine


def main() -> int:
    with engine.begin() as conn:
        conn.execute(
            text("ALTER TABLE postings ADD COLUMN IF NOT EXISTS canonical_id uuid;")
        )
        # Add the FK only if it doesn't already exist (Postgres-specific approach).
        conn.execute(
            text(
                """
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM pg_constraint WHERE conname = 'postings_canonical_id_fkey'
                    ) THEN
                        ALTER TABLE postings
                        ADD CONSTRAINT postings_canonical_id_fkey
                        FOREIGN KEY (canonical_id) REFERENCES postings(id) ON DELETE SET NULL;
                    END IF;
                END$$;
                """
            )
        )

    print("[OK] migration applied: postings.canonical_id column + FK ready")
    return 0


if __name__ == "__main__":
    sys.exit(main())
