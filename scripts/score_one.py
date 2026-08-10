"""Score the most recent posting against your profile using Claude Sonnet.

Doesn't persist — just prints the result. Persistence comes in 3.4.

Run:
    python scripts/score_one.py
"""

import logging
import sys

from sqlalchemy import select

from applytrak.db import session_scope
from applytrak.llm.score_prompt import score_posting
from applytrak.models import Posting, Profile
from applytrak.profile_config import ProfileConfig
from applytrak.schemas import ParsedJD

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


def _profile_to_config(profile: Profile) -> ProfileConfig:
    return ProfileConfig(
        resume_text=profile.resume_text,
        target_yoe_min=profile.target_yoe_min,
        target_yoe_max=profile.target_yoe_max,
        target_locations=profile.target_locations,
        remote_ok=profile.remote_ok,
        must_have_skills=profile.must_have_skills,
        nice_to_have_skills=profile.nice_to_have_skills,
        excluded_keywords=profile.excluded_keywords,
    )


def _posting_to_parsed(p: Posting) -> ParsedJD:
    return ParsedJD(
        company=p.company,
        title=p.title,
        yoe_min=p.yoe_min,
        yoe_max=p.yoe_max,
        location=p.location,
        is_remote=p.is_remote,
        is_hybrid=p.is_hybrid,
        must_have_skills=p.must_have_skills,
        nice_to_have_skills=p.nice_to_have_skills,
        comp_min=p.comp_min,
        comp_max=p.comp_max,
        comp_currency=p.comp_currency,
        parse_confidence=p.parse_confidence,
        parse_notes=p.parse_notes,
    )


def main() -> int:
    with session_scope() as session:
        profile = session.get(Profile, 1)
        if profile is None:
            print("[FAIL] No profile in DB. Run scripts/seed_profile.py first.", file=sys.stderr)
            return 1

        posting = session.scalar(
            select(Posting).order_by(Posting.parsed_at.desc()).limit(1)
        )
        if posting is None:
            print("[FAIL] No postings in DB. Run scripts/parse_pending.py first.", file=sys.stderr)
            return 1

        profile_cfg = _profile_to_config(profile)
        parsed_jd = _posting_to_parsed(posting)
        company = posting.company
        title = posting.title

    print(f"Scoring: {company} | {title}\n")

    judgment = score_posting(parsed_jd, profile_cfg)

    print("--- RelevanceJudgment ---")
    print(f"  score:             {judgment.score:.2f}")
    print(f"  one_line_summary:  {judgment.one_line_summary}")
    print(f"  yoe_match:         {judgment.yoe_match}")
    print(f"  location_match:    {judgment.location_match}")
    print(f"  skills_matched:    {judgment.skills_matched}")
    print(f"  skills_missing:    {judgment.skills_missing}")
    print(f"  hard_blockers:     {judgment.hard_blockers}")
    print("\n  reasoning:")
    print(f"    {judgment.reasoning}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
