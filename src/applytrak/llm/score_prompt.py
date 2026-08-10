"""Score a parsed JD against a candidate profile via the configured LLM provider.

Public API:
    score_posting(parsed_jd, profile) -> RelevanceJudgment

The rubric + resume + profile config go in the system block, which is stable
across every posting in a batch. On the Anthropic path the provider layer sends
it with prompt caching, so back-to-back calls only pay full input cost once.
"""

from applytrak.llm.providers import generate_structured
from applytrak.profile_config import ProfileConfig
from applytrak.schemas import ParsedJD, RelevanceJudgment

TOOL_NAME = "judge_relevance"

SCORING_SYSTEM_PROMPT = """You are evaluating whether a job posting is a strong match for a \
specific candidate. Be honest and discriminating — most postings are not perfect fits, \
and a low score is the right answer when the fit is weak.

Candidate resume:
<resume>
{resume_text}
</resume>

Candidate targeting (explicit preferences):
- Target YOE: {yoe_range}
- Target locations: {target_locations}
- Remote OK: {remote_ok}
- Must-have skills the candidate has: {must_have_skills}
- Nice-to-have skills the candidate has: {nice_to_have_skills}
- Excluded keywords (auto-reject if any appear in JD): {excluded_keywords}

Scoring rubric (0.0 to 1.0):
- Skills overlap (40%): How many of the JD's must_have_skills does the candidate have? \
  Weight by importance.
- YOE alignment (25%): Does the candidate's experience fall in the JD's required range? \
  Slightly under is OK; way over or way under is not.
- Location/remote fit (15%): Does the JD's location work given the candidate's targets \
  and remote_ok preference?
- Domain/seniority match (20%): Does the role type and seniority feel right based on the \
  resume's overall narrative (not just keywords)?

Calibrate your distribution:
- 0.85-1.0: Strong fit on all four axes. Apply.
- 0.65-0.85: Good fit with one weak axis. Worth a look.
- 0.40-0.65: Mixed. Skim, probably skip.
- Below 0.40: Poor fit. Skip.

Set hard_blockers when the posting should be auto-rejected regardless of score:
- JD requires significantly more YOE than candidate has (e.g., 8+ when candidate has 2)
- On-site only in a city the candidate doesn't target, with no remote option
- Hard credential requirements the candidate lacks (PhD, security clearance)
- Any of the candidate's excluded_keywords appear in the JD

For one_line_summary, write ONE line ≤ 160 characters that the candidate can scan in 2 seconds:
- "Strong RAG match at Anthropic, remote, 2-4 YOE — apply"
- "Partial match (missing K8s), hybrid NYC — skip"
- "Heavy backend role, on-site SF only — skip"
Do NOT write multiple sentences here.

Return your structured judgment."""


USER_PROMPT = """Job posting (parsed):
<jd>
{parsed_jd_json}
</jd>"""


def _format_yoe_range(min_y: int | None, max_y: int | None) -> str:
    if min_y is None and max_y is None:
        return "any"
    return f"{min_y or 0}-{max_y or '∞'} years"


def _build_system_block(profile: ProfileConfig) -> str:
    """Render the cached system prefix from a profile.

    Stable across every posting in a batch — that's why it's worth caching.
    """
    return SCORING_SYSTEM_PROMPT.format(
        resume_text=profile.resume_text,
        yoe_range=_format_yoe_range(profile.target_yoe_min, profile.target_yoe_max),
        target_locations=", ".join(profile.target_locations) or "(any)",
        remote_ok=profile.remote_ok,
        must_have_skills=", ".join(profile.must_have_skills) or "(none)",
        nice_to_have_skills=", ".join(profile.nice_to_have_skills) or "(none)",
        excluded_keywords=", ".join(profile.excluded_keywords) or "(none)",
    )


def score_posting(parsed_jd: ParsedJD, profile: ProfileConfig) -> RelevanceJudgment:
    """Score a parsed JD against a profile via the configured provider.

    Raises pydantic.ValidationError if the model returns malformed output.
    Raises ValueError if it returns no structured payload.
    """
    return generate_structured(
        task="score",
        system=_build_system_block(profile),
        user=USER_PROMPT.format(parsed_jd_json=parsed_jd.model_dump_json(indent=2)),
        schema=RelevanceJudgment,
        max_tokens=2048,
        tool_name=TOOL_NAME,
    )
