"""SQLAlchemy ORM models.

Add new tables in their respective phases:
  - raw_postings     (Phase 1) — raw fetched JDs
  - postings         (Phase 2) — parsed JDs
  - profile          (Phase 3) — your resume + targeting
  - relevance_scores (Phase 3) — scoring output
  - application_state (later)
  - digests           (Phase 6)
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, UUID
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


class Posting(Base):
    __tablename__ = "postings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    raw_posting_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("raw_postings.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )

    company: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)

    yoe_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    yoe_max: Mapped[int | None] = mapped_column(Integer, nullable=True)

    location: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_remote: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_hybrid: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    must_have_skills: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, default=list
    )
    nice_to_have_skills: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, default=list
    )

    comp_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    comp_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    comp_currency: Mapped[str | None] = mapped_column(String(8), nullable=True)

    parse_confidence: Mapped[float] = mapped_column(Float, nullable=False)
    parse_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    parsed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<Posting company={self.company!r} title={self.title!r}>"
