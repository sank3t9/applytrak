"""Parse a raw JD into structured fields via the configured LLM provider.

Public API:
    parse_jd(raw_text) -> ParsedJD

Includes:
  - parse cache keyed by sha256(raw_text) + provider/model (Redis or Postgres)
  - per-minute rate limit, applied inside the provider layer
"""

import logging

from applytrak.llm.cache import parse_cache_get, parse_cache_set
from applytrak.llm.providers import generate_structured
from applytrak.schemas import ParsedJD

logger = logging.getLogger(__name__)

TOOL_NAME = "extract_job_posting"

PARSE_PROMPT = """You are extracting structured data from a job posting on \
Hacker News' "Ask HN: Who is hiring?" monthly thread.

Job posting:
<jd>
{raw_text}
</jd>

Common HN format: "Company | Location | Job Type | URL", followed by description \
and sometimes a list of specific roles.

Extraction rules — be conservative, do not infer:
- For YOE: only extract numbers explicitly mentioned. Do not infer from "senior" \
or "junior" labels. Note implied seniority in parse_notes.
- For location: capture the location string as written. Set is_remote=true if \
remote is mentioned anywhere; is_hybrid=true if hybrid is mentioned.
- For comp: only extract numbers explicitly stated. "Competitive" → null.
- For skills: extract specific technologies, languages, frameworks. Skip soft skills \
("communication", "team player", etc.).

For title:
- If multiple roles are listed, pick the most prominent one (typically first or most senior).
- Note any additional roles in parse_notes (e.g., "also lists Senior SWE and QA Lead").

For parse_confidence:
- 0.9-1.0: clear, structured, all key fields present
- 0.6-0.9: most fields clear, some inference needed
- 0.3-0.6: vague or marketing-heavy
- 0.0-0.3: barely a job posting

Return the structured extraction."""


def parse_jd(raw_text: str) -> ParsedJD:
    """Parse a raw JD into a ParsedJD via the configured provider.

    Cache: checked first; hits skip the LLM call entirely.
    Rate limit: applied inside the provider layer.

    Raises pydantic.ValidationError if the model returns malformed output.
    Raises ValueError if it returns no structured payload.
    """
    cached = parse_cache_get(raw_text)
    if cached is not None:
        logger.info("parse cache HIT (text len=%d)", len(raw_text))
        return cached

    parsed = generate_structured(
        task="parse",
        user=PARSE_PROMPT.format(raw_text=raw_text),
        schema=ParsedJD,
        max_tokens=2048,
        tool_name=TOOL_NAME,
    )
    parse_cache_set(raw_text, parsed)
    return parsed
