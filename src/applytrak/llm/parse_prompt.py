"""Parse a raw JD into structured fields using Claude (via tool use).

Public API:
    parse_jd(raw_text) -> ParsedJD

Includes:
  - Redis-backed parse cache (sha256(raw_text) → ParsedJD)
  - Per-minute rate limit on the Anthropic call
"""

import logging

from applytrak.config import settings
from applytrak.llm.cache import parse_cache_get, parse_cache_set
from applytrak.llm.client import client
from applytrak.rate_limit import acquire_rate_limit
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

Use the extract_job_posting tool to return your structured extraction."""


def parse_jd(raw_text: str) -> ParsedJD:
    """Parse a raw JD into a ParsedJD via Claude tool use.

    Cache: checks Redis first; cache hits skip the LLM call entirely.
    Rate limit: blocks if Anthropic RPM budget for this minute is spent.

    Raises pydantic.ValidationError if Claude returns malformed structured output.
    Raises ValueError if Claude doesn't call the tool at all.
    """
    cached = parse_cache_get(raw_text)
    if cached is not None:
        logger.info("parse cache HIT (text len=%d)", len(raw_text))
        return cached

    with acquire_rate_limit("anthropic", max_per_minute=settings.anthropic_rpm):
        response = client.messages.create(
            model=settings.anthropic_model_parse,
            max_tokens=2048,
            tools=[
                {
                    "name": TOOL_NAME,
                    "description": "Extract structured fields from a job posting.",
                    "input_schema": ParsedJD.model_json_schema(),
                }
            ],
            tool_choice={"type": "tool", "name": TOOL_NAME},
            messages=[{"role": "user", "content": PARSE_PROMPT.format(raw_text=raw_text)}],
        )

    for block in response.content:
        if block.type == "tool_use" and block.name == TOOL_NAME:
            parsed = ParsedJD(**block.input)
            parse_cache_set(raw_text, parsed)
            return parsed

    raise ValueError(f"Claude did not call {TOOL_NAME!r} tool. Response: {response.content!r}")
