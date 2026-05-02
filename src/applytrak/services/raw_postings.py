"""Operations on the raw_postings table.

Bridges the source layer (Pydantic FetchedPosting) and the model layer
(SQLAlchemy RawPosting). Keeps both layers free of cross-concern code.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from applytrak.models import RawPosting
from applytrak.sources.hn import FetchedPosting


def save_raw_posting(session: Session, fetched: FetchedPosting) -> tuple[RawPosting, bool]:
    """Persist a fetched posting if not already in the DB.

    Returns (raw_posting, created) where `created` is True if we inserted a new row,
    False if a matching (source, source_id) row already existed.
    """
    existing = session.scalar(
        select(RawPosting).where(
            RawPosting.source == fetched.source,
            RawPosting.source_id == fetched.source_id,
        )
    )
    if existing is not None:
        return existing, False

    new_posting = RawPosting(
        source=fetched.source,
        source_id=fetched.source_id,
        url=fetched.url,
        raw_text=fetched.raw_text,
    )
    session.add(new_posting)
    session.flush()
    return new_posting, True
