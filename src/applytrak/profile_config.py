"""Pydantic schema for profile.yaml.

Used by scripts/seed_profile.py to validate the YAML before persisting.
"""

from pydantic import BaseModel, Field


class ProfileConfig(BaseModel):
    """Validates the structure of profile.yaml."""

    resume_text: str = Field(min_length=50, description="Your resume as plain text.")

    target_yoe_min: int | None = Field(default=None, ge=0)
    target_yoe_max: int | None = Field(default=None, ge=0)

    target_locations: list[str] = Field(
        default_factory=list,
        description="Locations you'd consider, e.g. 'San Francisco', 'Remote (US)'.",
    )
    remote_ok: bool = Field(default=True, description="Are remote roles acceptable?")

    must_have_skills: list[str] = Field(default_factory=list)
    nice_to_have_skills: list[str] = Field(default_factory=list)
    excluded_keywords: list[str] = Field(
        default_factory=list,
        description="If a JD contains any of these, treat it as a hard reject.",
    )
