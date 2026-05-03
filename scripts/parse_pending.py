"""Parse all unparsed raw_postings using Claude.

Run periodically (in production, every N minutes via APScheduler).
Idempotent: re-runs skip already-parsed postings.

Run:
    python scripts/parse_pending.py
"""

import logging
import sys

from applytrak.db import session_scope
from applytrak.llm.parse_prompt import parse_jd
from applytrak.services.postings import fetch_unparsed_raw_postings, save_posting

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


def main() -> int:
    # Step 1: snapshot the work — short DB session, no LLM held inside it.
    with session_scope() as session:
        unparsed = fetch_unparsed_raw_postings(session)
        if not unparsed:
            print("[OK] No unparsed raw_postings. Nothing to do.")
            return 0
        targets = [(r.id, r.raw_text, r.url) for r in unparsed]

    print(f"[START] Parsing {len(targets)} raw_postings...\n")

    inserted = 0
    skipped = 0
    failed = 0

    for raw_id, raw_text, url in targets:
        print(f"[PARSE] {url}")
        try:
            parsed = parse_jd(raw_text)
        except Exception as e:
            print(f"  [FAIL] parse_jd raised: {type(e).__name__}: {e}")
            failed += 1
            continue

        print(f"  -> {parsed.company} | {parsed.title}  (confidence={parsed.parse_confidence:.2f})")

        # Step 3: short DB session per save, no LLM call inside it.
        with session_scope() as session:
            posting, created = save_posting(session, raw_id, parsed)
            if created:
                inserted += 1
                print(f"  [OK]   inserted posting id={posting.id}\n")
            else:
                skipped += 1
                print(f"  [SKIP] already had posting id={posting.id}\n")

    print(f"[DONE] inserted={inserted} skipped={skipped} failed={failed}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
