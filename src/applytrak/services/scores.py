"""Operations on the relevance_scores table."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from applytrak.models import Posting, RelevanceScore
from applytrak.schemas import RelevanceJudgment


def fetch_unscored_postings(session: Session, limit: int | None = None) -> list[Posting]:
    """Return canonical (non-duplicate) parsed postings that don't yet have a relevance score."""
    stmt = (
        select(Posting)
        .where(Posting.canonical_id.is_(None))
        .where(~Posting.id.in_(select(RelevanceScore.posting_id)))
        .order_by(Posting.parsed_at)
    )
    if limit is not None:
        stmt = stmt.limit(limit)
    return list(session.scalars(stmt))


def save_score(
    session: Session,
    posting_id: uuid.UUID,
    judgment: RelevanceJudgment,
) -> tuple[RelevanceScore, bool]:
    """Persist a relevance judgment. Returns (score, created).

    Idempotent: if a score already exists for this posting_id, return it unchanged.
    """
    existing = session.get(RelevanceScore, posting_id)
    if existing is not None:
        return existing, False

    score = RelevanceScore(
        posting_id=posting_id,
        score=judgment.score,
        reasoning=judgment.reasoning,
        skills_matched=judgment.skills_matched,
        skills_missing=judgment.skills_missing,
        yoe_match=judgment.yoe_match,
        location_match=judgment.location_match,
        hard_blockers=judgment.hard_blockers,
        one_line_summary=judgment.one_line_summary,
    )
    session.add(score)
    session.flush()
    return score, True
