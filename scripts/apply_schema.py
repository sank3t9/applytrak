"""Bring the database schema fully up to date. Safe to run any time.

Runs table creation and every column migration in order. This is the single
command to run after pulling changes or pointing at a new database — the
individual scripts still exist, but running them piecemeal makes it easy to
miss one and hit "column ... does not exist" at runtime.

Run:
    python scripts/apply_schema.py
"""

import sys
from collections.abc import Callable

import init_db
import migrate_add_canonical_id
import migrate_add_embedding_model
import migrate_add_embeddings
import migrate_add_posted_at

# Order matters: tables first, then columns added to them.
STEPS: list[tuple[str, Callable[[], int]]] = [
    ("init_db", init_db.main),
    ("migrate_add_embeddings", migrate_add_embeddings.main),
    ("migrate_add_canonical_id", migrate_add_canonical_id.main),
    ("migrate_add_embedding_model", migrate_add_embedding_model.main),
    ("migrate_add_posted_at", migrate_add_posted_at.main),
]


def main() -> int:
    for name, step in STEPS:
        print(f"\n--- {name} ---")
        code = step()
        if code != 0:
            print(f"[FAIL] {name} exited {code}", file=sys.stderr)
            return code

    print(f"\n[OK] schema up to date ({len(STEPS)} steps)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
