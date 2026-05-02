"""SQLAlchemy ORM models.

Add new tables in their respective phases:
  - raw_postings  (Phase 1) — raw fetched JDs
  - postings      (Phase 2) — parsed JDs
  - profile       (Phase 3) — your resume + targeting
  - relevance_scores (Phase 3) — scoring output
  - application_state (later)
  - digests          (Phase 6)
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class all ORM models inherit from."""


class RawPosting(Base):
    __tablename__ = "raw_postings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    source_id: Mapped[str] = mapped_column(String(128), nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (UniqueConstraint("source", "source_id", name="uq_source_source_id"),)

    def __repr__(self) -> str:
        return f"<RawPosting source={self.source} source_id={self.source_id}>"
