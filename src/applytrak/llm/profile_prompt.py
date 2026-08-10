"""Turn a raw resume into targeting preferences via the configured LLM provider.

Lets a visitor paste a resume and get matches without filling in a form: the
LLM infers what the personal deployment reads from profile.yaml.

Public API:
    extract_profile(resume_text) -> ExtractedProfile
    to_profile_config(resume_text, extracted) -> ProfileConfig
"""

import logging

from applytrak.llm.providers import generate_structured
from applytrak.profile_config import ProfileConfig
from applytrak.schemas import ExtractedProfile

logger = logging.getLogger(__name__)

TOOL_NAME = "extract_candidate_profile"

MAX_SKILLS = 15

PROFILE_PROMPT = """You are extracting a candidate's job-search targeting \
preferences from their resume.

Resume:
<resume>
{resume_text}
</resume>

Rules — be conservative, do not invent:
- Only list skills actually evidenced in the resume. Skip soft skills \
("communication", "team player") and list concrete technologies, languages, \
frameworks, and tools.
- must_have_skills: what they clearly know well (appears in real projects or \
roles). nice_to_have_skills: mentioned once or in passing.
- For YOE: count professional work history. Internships shorter than 6 months \
don't count. If the resume has no dated work history, leave total_yoe null.
- Derive the target range around their actual experience: target_yoe_min is \
about total_yoe - 2 (never below 0), target_yoe_max about total_yoe + 3. \
Leave both null when total_yoe is null.
- target_locations: only places supported by the resume (where they worked, \
studied, or state they want). Leave empty rather than guessing a country.
- remote_ok: true unless the resume explicitly rules remote out.

Return the structured profile."""


def extract_profile(resume_text: str) -> ExtractedProfile:
    """Infer targeting preferences from a resume.

    Raises pydantic.ValidationError if the model returns malformed output.
    """
    extracted = generate_structured(
        task="parse",
        user=PROFILE_PROMPT.format(resume_text=resume_text),
        schema=ExtractedProfile,
        max_tokens=2048,
        tool_name=TOOL_NAME,
    )
    logger.info(
        "extracted profile: yoe=%s-%s skills=%d locations=%s",
        extracted.target_yoe_min,
        extracted.target_yoe_max,
        len(extracted.must_have_skills),
        extracted.target_locations,
    )
    return extracted


def to_profile_config(resume_text: str, extracted: ExtractedProfile) -> ProfileConfig:
    """Combine a resume with its extracted preferences into a scorer-ready profile.

    Same shape the personal deployment loads from profile.yaml, so the scoring
    prompt is identical for visitors and for the owner.
    """
    return ProfileConfig(
        resume_text=resume_text,
        target_yoe_min=extracted.target_yoe_min,
        target_yoe_max=extracted.target_yoe_max,
        target_locations=extracted.target_locations,
        remote_ok=extracted.remote_ok,
        must_have_skills=extracted.must_have_skills[:MAX_SKILLS],
        nice_to_have_skills=extracted.nice_to_have_skills[:MAX_SKILLS],
        excluded_keywords=[],
    )
