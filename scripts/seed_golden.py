"""Bootstrap tests/golden/jds.jsonl from the parsed postings in your DB.

Writes one JSONL entry per posting:
    {"id": "<hn_comment_id>", "url": "...", "raw_text": "...", "expected": {...}}

The `expected` block starts as Haiku's extraction. Your job: open the file
and correct any mistakes — for the golden set to be useful, the labels must be
human-verified, not LLM-generated.

Idempotent only in the sense of overwriting — re-running replaces the file.
Don't run after you've made corrections, or you'll lose them.

Run:
    python scripts/seed_golden.py
"""

import json
import sys
from pathlib import Path

from sqlalchemy import select

from applytrak.db import session_scope
from applytrak.models import Posting, RawPosting
from applytrak.schemas import ParsedJD

OUTPUT_PATH = Path("tests/golden/jds.jsonl")


def main() -> int:
    if OUTPUT_PATH.exists():
        print(
            f"[ABORT] {OUTPUT_PATH} already exists. "
            "Delete it first if you really want to re-bootstrap "
            "(this would overwrite your labels).",
            file=sys.stderr,
        )
        return 1

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    with session_scope() as session, OUTPUT_PATH.open("w", encoding="utf-8") as f:
        rows = session.execute(
            select(Posting, RawPosting.raw_text, RawPosting.url, RawPosting.source_id)
            .join(RawPosting, Posting.raw_posting_id == RawPosting.id)
            .order_by(Posting.parsed_at)
        ).all()

        count = 0
        for posting, raw_text, url, source_id in rows:
            expected = ParsedJD.model_validate(posting, from_attributes=True).model_dump()
            entry = {
                "id": source_id,
                "url": url,
                "raw_text": raw_text,
                "expected": expected,
            }
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
            count += 1

    print(f"[OK] wrote {count} entries to {OUTPUT_PATH}")
    print()
    print("NEXT — open the file and review every `expected` block:")
    print(f"  code {OUTPUT_PATH}")
    print()
    print("Read the raw_text first, then check the LLM's extraction. Common errors")
    print("to look for:")
    print("  - hallucinated YOE (LLM inferred from 'senior' label)")
    print("  - wrong company name on multi-company posts")
    print("  - missed must-have skills")
    print("  - wrong is_remote/is_hybrid based on ambiguous wording")
    return 0


if __name__ == "__main__":
    sys.exit(main())
