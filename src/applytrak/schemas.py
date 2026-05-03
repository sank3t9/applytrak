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
