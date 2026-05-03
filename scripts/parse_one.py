"""Parse the most recently fetched raw_posting using Claude.

Doesn't persist — just prints the structured result. Persistence comes in 2.4.

Run:
    python scripts/parse_one.py
"""

import logging
import sys

from sqlalchemy import select

from applytrak.db import session_scope
from applytrak.llm.parse_prompt import parse_jd
from applytrak.models import RawPosting

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


def main() -> int:
    with session_scope() as session:
        raw = session.scalar(
            select(RawPosting).order_by(RawPosting.fetched_at.desc()).limit(1)
        )
        if raw is None:
            print("[FAIL] No raw_postings in DB. Run scripts/save_one.py first.", file=sys.stderr)
            return 1

        print(f"Parsing raw_posting id={raw.id}")
        print(f"  source:    {raw.source} / {raw.source_id}")
        print(f"  url:       {raw.url}")
        print(f"  text_len:  {len(raw.raw_text)} chars\n")

        parsed = parse_jd(raw.raw_text)

    print("--- ParsedJD ---")
    print(f"  company:            {parsed.company!r}")
    print(f"  title:              {parsed.title!r}")
    print(f"  yoe:                {parsed.yoe_min} - {parsed.yoe_max}")
    print(f"  location:           {parsed.location!r}")
    print(f"  is_remote:          {parsed.is_remote}")
    print(f"  is_hybrid:          {parsed.is_hybrid}")
    print(f"  must_have_skills:   {parsed.must_have_skills}")
    print(f"  nice_to_have:       {parsed.nice_to_have_skills}")
    print(f"  comp:               {parsed.comp_min} - {parsed.comp_max} {parsed.comp_currency!r}")
    print(f"  parse_confidence:   {parsed.parse_confidence:.2f}")
    print(f"  parse_notes:        {parsed.parse_notes!r}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
