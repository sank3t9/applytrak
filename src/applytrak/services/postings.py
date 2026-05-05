"""Operations on the postings table."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from applytrak.models import Posting, RawPosting
from applytrak.schemas import ParsedJD


def fetch_unparsed_raw_postings(session: Session, limit: int | None = None) -> list[RawPosting]:
    """Return raw_postings that don't yet have a corresponding parsed posting."""
    stmt = (
        select(RawPosting)
        .where(~RawPosting.id.in_(select(Posting.raw_posting_id)))
        .order_by(RawPosting.fetched_at)
    )
    if limit is not None:
        stmt = stmt.limit(limit)
    return list(session.scalars(stmt))


def save_posting(
    session: Session,
    raw_posting_id: uuid.UUID,
    parsed: ParsedJD,
) -> tuple[Posting, bool]:
    """Persist a parsed JD. Returns (posting, created).

    Idempotent: if a posting already exists for this raw_posting_id, return it
    unchanged with created=False.
    """
    existing = session.scalar(select(Posting).where(Posting.raw_posting_id == raw_posting_id))
    if existing is not None:
        return existing, False

    posting = Posting(
        raw_posting_id=raw_posting_id,
        company=parsed.company,
        title=parsed.title,
        yoe_min=parsed.yoe_min,
        yoe_max=parsed.yoe_max,
        location=parsed.location,
        is_remote=parsed.is_remote,
        is_hybrid=parsed.is_hybrid,
        must_have_skills=parsed.must_have_skills,
        nice_to_have_skills=parsed.nice_to_have_skills,
        comp_min=parsed.comp_min,
        comp_max=parsed.comp_max,
        comp_currency=parsed.comp_currency,
        parse_confidence=parsed.parse_confidence,
        parse_notes=parsed.parse_notes,
    )
    session.add(posting)
    session.flush()
    return posting, True
