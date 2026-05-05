"""LLM-as-Judge eval of the scorer.

Pulls N scored postings from the DB, has a separate Claude call grade each
score's reasoning quality and check whether the score is defensible.

Cost: ~$0.015 per posting × N. Default N=5 = ~$0.08 per run.

Run:
    pytest tests/test_scorer_judge.py -s
"""

import os

import pytest
from sqlalchemy import select

from applytrak.db import session_scope
from applytrak.llm.judge_prompt import judge_score
from applytrak.models import Posting, Profile, RelevanceScore
from applytrak.profile_config import ProfileConfig
from applytrak.schemas import JudgeVerdict, ParsedJD, RelevanceJudgment

# How many scored postings to judge. Override with env var.
JUDGE_SAMPLE_SIZE = int(os.getenv("JUDGE_SAMPLE_SIZE", "5"))

# Pass thresholds — tune after first run.
MIN_REASONING_QUALITY = 0.60
MIN_SCORE_APPROPRIATE_RATE = 0.80


def _load_judge_inputs() -> list[tuple[str, ParsedJD, ProfileConfig, RelevanceJudgment]]:
    """Snapshot N scored postings + profile out of the DB into pure-Pydantic tuples."""
    with session_scope() as session:
        profile = session.get(Profile, 1)
        if profile is None:
            return []
        profile_cfg = ProfileConfig.model_validate(profile, from_attributes=True)

        rows = list(
            session.scalars(
                select(Posting)
                .join(RelevanceScore, Posting.id == RelevanceScore.posting_id)
                .where(Posting.canonical_id.is_(None))
                .order_by(RelevanceScore.score.desc())
                .limit(JUDGE_SAMPLE_SIZE)
            )
        )
        if not rows:
            return []

        # Re-fetch scores in the same session
        out = []
        for posting in rows:
            score = session.get(RelevanceScore, posting.id)
            if score is None:
                continue
            parsed = ParsedJD.model_validate(posting, from_attributes=True)
            judgment = RelevanceJudgment.model_validate(score, from_attributes=True)
            out.append((str(posting.id), parsed, profile_cfg, judgment))
        return out


JUDGE_INPUTS = _load_judge_inputs()


@pytest.mark.skipif(not JUDGE_INPUTS, reason="No scored postings in DB to judge")
@pytest.mark.parametrize(
    "posting_id,parsed,profile,judgment",
    JUDGE_INPUTS,
    ids=[t[0] for t in JUDGE_INPUTS],
)
def test_scorer_reasoning_quality(
    posting_id: str,
    parsed: ParsedJD,
    profile: ProfileConfig,
    judgment: RelevanceJudgment,
    judge_results: dict,
) -> None:
    verdict: JudgeVerdict = judge_score(parsed, profile, judgment)
    judge_results[posting_id] = verdict

    assert verdict.reasoning_quality >= MIN_REASONING_QUALITY, (
        f"Posting {posting_id}: reasoning quality {verdict.reasoning_quality:.2f} "
        f"< {MIN_REASONING_QUALITY}.\n"
        f"Critique: {verdict.critique}\n"
        f"Flags: {verdict.flags}"
    )
