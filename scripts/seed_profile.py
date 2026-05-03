"""Load profile.yaml into the profile table.

Idempotent: first run inserts, subsequent runs update the same row (id=1).

Run:
    python scripts/seed_profile.py
"""

import sys
from pathlib import Path

import yaml

from applytrak.db import session_scope
from applytrak.models import Profile
from applytrak.profile_config import ProfileConfig

PROFILE_PATH = Path("profile.yaml")


def main() -> int:
    if not PROFILE_PATH.exists():
        print(
            f"[FAIL] {PROFILE_PATH} not found. "
            "Copy profile.example.yaml to profile.yaml and fill it in.",
            file=sys.stderr,
        )
        return 1

    raw = yaml.safe_load(PROFILE_PATH.read_text(encoding="utf-8"))
    config = ProfileConfig(**raw)

    with session_scope() as session:
        existing = session.get(Profile, 1)
        if existing is None:
            profile = Profile(
                id=1,
                resume_text=config.resume_text,
                target_yoe_min=config.target_yoe_min,
                target_yoe_max=config.target_yoe_max,
                target_locations=config.target_locations,
                remote_ok=config.remote_ok,
                must_have_skills=config.must_have_skills,
                nice_to_have_skills=config.nice_to_have_skills,
                excluded_keywords=config.excluded_keywords,
            )
            session.add(profile)
            verb = "INSERTED"
        else:
            existing.resume_text = config.resume_text
            existing.target_yoe_min = config.target_yoe_min
            existing.target_yoe_max = config.target_yoe_max
            existing.target_locations = config.target_locations
            existing.remote_ok = config.remote_ok
            existing.must_have_skills = config.must_have_skills
            existing.nice_to_have_skills = config.nice_to_have_skills
            existing.excluded_keywords = config.excluded_keywords
            verb = "UPDATED"

    print(f"[OK] {verb} profile id=1")
    print(f"     resume_text:        {len(config.resume_text)} chars")
    print(f"     target_yoe:         {config.target_yoe_min} - {config.target_yoe_max}")
    print(f"     target_locations:   {config.target_locations}")
    print(f"     remote_ok:          {config.remote_ok}")
    print(f"     must_have_skills:   {config.must_have_skills}")
    print(f"     nice_to_have:       {config.nice_to_have_skills}")
    print(f"     excluded_keywords:  {config.excluded_keywords}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
