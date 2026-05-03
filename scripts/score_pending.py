"""Score all unscored postings against the profile using Claude Sonnet.

Idempotent: re-runs skip already-scored postings.

Run:
    python scripts/score_pending.py
"""

import logging
import sys

from applytrak.db import session_scope
from applytrak.llm.score_prompt import score_posting
from applytrak.models import Profile
from applytrak.profile_config import ProfileConfig
from applytrak.schemas import ParsedJD
from applytrak.services.scores import fetch_unscored_postings, save_score

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


def main() -> int:
    # Stage 1: snapshot profile + work-list, then close the session.
    with session_scope() as session:
        profile = session.get(Profile, 1)
        if profile is None:
            print("[FAIL] No profile in DB. Run scripts/seed_profile.py first.", file=sys.stderr)
            return 1
        profile_cfg = ProfileConfig.model_validate(profile, from_attributes=True)

        unscored = fetch_unscored_postings(session)
        if not unscored:
            print("[OK] No unscored postings. Nothing to do.")
            return 0

        targets = [
            (
                p.id,
                ParsedJD.model_validate(p, from_attributes=True),
                p.company,
                p.title,
            )
            for p in unscored
        ]

    print(f"[START] Scoring {len(targets)} postings...\n")

    inserted = 0
    skipped = 0
    failed = 0

    for posting_id, parsed_jd, company, title in targets:
        print(f"[SCORE] {company} | {title}")
        try:
            judgment = score_posting(parsed_jd, profile_cfg)
        except Exception as e:
            print(f"  [FAIL] score_posting raised: {type(e).__name__}: {e}")
            failed += 1
            continue

        print(f"  -> score={judgment.score:.2f}  {judgment.one_line_summary}")

        with session_scope() as session:
            _, created = save_score(session, posting_id, judgment)
            if created:
                inserted += 1
                print("  [OK]   inserted score\n")
            else:
                skipped += 1
                print("  [SKIP] already had score\n")

    print(f"[DONE] inserted={inserted} skipped={skipped} failed={failed}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
