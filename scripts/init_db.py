"""Create all tables defined in applytrak.models.

Idempotent: running multiple times is safe (CREATE TABLE IF NOT EXISTS).

Run:
    python scripts/init_db.py
"""

import sys

from applytrak.db import engine
from applytrak.models import Base


def main() -> int:
    print("Creating tables...")
    Base.metadata.create_all(engine)

    print("Tables in database:")
    for table_name in Base.metadata.tables:
        print(f"  - {table_name}")

    print("\n[OK] schema initialized.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
