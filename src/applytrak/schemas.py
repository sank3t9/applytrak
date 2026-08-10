"""Pydantic schemas for LLM structured output.

These schemas are the *contract* with Claude:
  "Return JSON that validates against this exact shape."

Keep them free of database concerns — they describe LLM output, not storage.
"""

from pydantic import BaseModel, Field


class ParsedJD(BaseModel):
    """Structured fields extracted from a raw job posting by Claude Haiku."""

    company: str = Field(description="Company name")
    title: str = Field(
        description=(
            "Job title. If multiple roles are listed in one posting, pick the most "
            "prominent or representative one."
        )
    )

    yoe_min: int | None = Field(
        default=None,
        description="Minimum years of experience required, or null if unspecified.",
    )
    yoe_max: int | None = Field(
        default=None,
        description="Maximum years of experience listed, or null if unspecified.",
    )

    location: str | None = Field(
        default=None,
        description=(
            "Primary location as written, e.g. 'San Francisco', 'Remote (US)', "
            "'NYC or Remote'. Null if unspecified."
        ),
    )
    is_remote: bool = Field(default=False, description="True if remote work is allowed.")
    is_hybrid: bool = Field(default=False, description="True if hybrid is allowed/required.")

    must_have_skills: list[str] = Field(
        default_factory=list,
        description="Hard requirements (e.g., 'Python', 'AWS', 'PhD').",
    )
    nice_to_have_skills: list[str] = Field(
        default_factory=list,
        description="Plus / bonus / preferred skills.",
    )

    comp_min: int | None = Field(
        default=None, description="Minimum compensation in stated currency, or null."
    )
    comp_max: int | None = Field(
        default=None, description="Maximum compensation in stated currency, or null."
    )
    comp_currency: str | None = Field(
        default=None,
        description="ISO currency code if stated (e.g., 'USD', 'EUR'), null otherwise.",
    )

    parse_confidence: float = Field(
        ge=0.0,
        le=1.0,
        description=(
            "How confident you are in this extraction. "
            "0.9-1.0: clear, structured posting. "
            "0.6-0.9: most fields clear. "
            "0.3-0.6: vague or marketing-heavy. "
            "0.0-0.3: barely a job posting."
        ),
    )
    parse_notes: str | None = Field(
        default=None,
        description=(
            "Free-form notes flagging ambiguity, missing fields, or unusual structure. "
            "E.g., 'YOE not stated, seniority implied as senior' or "
            "'Posting lists 4 roles; extracted the most senior'."
        ),
    )


class RelevanceJudgment(BaseModel):
    """Structured scoring output produced by Claude Sonnet against a parsed JD + profile."""

    score: float = Field(
        ge=0.0,
        le=1.0,
        description="Overall relevance score, 0.0 (no fit) to 1.0 (perfect fit).",
    )
    reasoning: str = Field(
        min_length=20,
        description=(
            "Two to three sentences explaining the score. "
            "Be specific about what matched and what didn't."
        ),
    )

    skills_matched: list[str] = Field(
        default_factory=list,
        description="Candidate skills explicitly matched by the JD's requirements.",
    )
    skills_missing: list[str] = Field(
        default_factory=list,
        description="JD must-have skills the candidate appears to lack.",
    )

    yoe_match: bool = Field(
        description=(
            "True if the candidate's YOE falls in the JD's required range, "
            "or if the JD didn't specify YOE."
        )
    )
    location_match: bool = Field(
        description=(
            "True if the JD's location works for the candidate (target locations, "
            "or remote when remote_ok=True)."
        )
    )

    hard_blockers: list[str] = Field(
        default_factory=list,
        description=(
            "Concrete reasons to auto-reject this posting regardless of score, "
            "e.g., 'requires 8+ YOE', 'on-site Berlin only', 'PhD required', "
            "'matches excluded keyword: Top Secret clearance'."
        ),
    )

    one_line_summary: str = Field(
        max_length=200,
        description=(
            "ONE short line for the digest, ≤ 160 characters. Must include role/company hint, "
            "key match signal, and a verdict word. "
            "Example: 'Strong RAG match at Anthropic, remote, 2-4 YOE — apply'."
        ),
    )


class JudgeVerdict(BaseModel):
    """LLM-as-Judge output: a structured grade on a scoring agent's reasoning."""

    reasoning_quality: float = Field(
        ge=0.0,
        le=1.0,
        description=(
            "How specific and well-grounded is the scorer's reasoning? "
            "1.0: cites specific skills, YOE numbers, location facts. "
            "0.5: mentions categories without specifics. "
            "0.0: vague hand-waving with no concrete references."
        ),
    )
    score_appropriate: bool = Field(
        description=(
            "Is the numeric score in a defensible range for the JD/profile? "
            "Use loose tolerance (±0.15)."
        )
    )
    flags: list[str] = Field(
        default_factory=list,
        description=(
            "Specific issues with the scorer's output, e.g.: "
            "'doesn't mention candidate YOE'; "
            "'overlooks excluded keyword in JD'; "
            "'generic reasoning, no resume-specific references'."
        ),
    )
    critique: str = Field(
        min_length=20,
        description="Two to four tight sentences (≤ 80 words) explaining the verdict.",
    )
