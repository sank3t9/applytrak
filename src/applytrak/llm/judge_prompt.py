"""LLM-as-Judge: grade the quality of a scorer's reasoning.

The judge is a separate LLM call evaluating the *scorer's output* against
the *original inputs*. It does NOT re-score; it grades the reasoning's
specificity, groundedness, and whether the score is in a defensible range.

The judge instructions + resume + candidate constraints go in the system block,
stable across an eval run — on the Anthropic path the provider layer sends it
with prompt caching so only the first judgment pays full input cost.

Public API:
    judge_score(parsed_jd, profile, judgment) -> JudgeVerdict
"""

from applytrak.llm.providers import generate_structured
from applytrak.profile_config import ProfileConfig
from applytrak.schemas import JudgeVerdict, ParsedJD, RelevanceJudgment

TOOL_NAME = "deliver_verdict"

JUDGE_SYSTEM_PROMPT = """You are evaluating the quality of an automated scoring \
agent that judges whether a job posting is a good fit for a specific candidate.

You will see the candidate's profile, the JD, and the scorer's output. \
Your job is to grade the *reasoning quality* and verify the score is defensible.

Candidate profile:
<resume>
{resume_text}
</resume>

Candidate constraints:
- Target YOE: {yoe_range}
- Target locations: {target_locations}
- Remote OK: {remote_ok}
- Must-have skills: {must_have_skills}

Grade strictly:
- reasoning_quality: 1.0 if the reasoning cites SPECIFIC skills/YOE numbers/ \
  locations from both the resume and the JD; 0.5 if it stays at category-level \
  ("backend match", "remote ok"); 0.0 if generic ("looks like a fit").
- score_appropriate: true if the numeric score is within ±0.15 of what a \
  reasonable human would assign; false otherwise.
- flags: list specific issues. Examples:
    "ignores candidate's excluded_keywords"
    "claims YOE match but JD lists '7+ years'"
    "doesn't justify why score is below 0.5"
- critique: 2-4 tight sentences (≤ 80 words) explaining your verdict.

Return your structured assessment."""


USER_PROMPT = """Job posting (parsed):
<jd>
{parsed_jd_json}
</jd>

The scorer produced:
<score>
{score:.2f}
</score>
<reasoning>
{reasoning}
</reasoning>
<one_line_summary>
{one_line_summary}
</one_line_summary>
<skills_matched>{skills_matched}</skills_matched>
<skills_missing>{skills_missing}</skills_missing>
<hard_blockers>{hard_blockers}</hard_blockers>"""


def _build_system_block(profile: ProfileConfig) -> str:
    """Render the cached system prefix from a profile.

    Stable across every judgment in a run — that's why it's worth caching.
    """
    yoe_range = (
        f"{profile.target_yoe_min or 0}-{profile.target_yoe_max or '∞'} years"
        if profile.target_yoe_min is not None or profile.target_yoe_max is not None
        else "any"
    )
    return JUDGE_SYSTEM_PROMPT.format(
        resume_text=profile.resume_text,
        yoe_range=yoe_range,
        target_locations=", ".join(profile.target_locations) or "(any)",
        remote_ok=profile.remote_ok,
        must_have_skills=", ".join(profile.must_have_skills) or "(none)",
    )


def judge_score(
    parsed_jd: ParsedJD, profile: ProfileConfig, judgment: RelevanceJudgment
) -> JudgeVerdict:
    """Grade a scorer's RelevanceJudgment via the configured provider."""
    user_text = USER_PROMPT.format(
        parsed_jd_json=parsed_jd.model_dump_json(indent=2),
        score=judgment.score,
        reasoning=judgment.reasoning,
        one_line_summary=judgment.one_line_summary,
        skills_matched=", ".join(judgment.skills_matched) or "(none)",
        skills_missing=", ".join(judgment.skills_missing) or "(none)",
        hard_blockers=", ".join(judgment.hard_blockers) or "(none)",
    )

    return generate_structured(
        task="score",
        system=_build_system_block(profile),
        user=user_text,
        schema=JudgeVerdict,
        max_tokens=1024,
        tool_name=TOOL_NAME,
    )
