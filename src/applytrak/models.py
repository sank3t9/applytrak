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

from pgvector.sqlalchemy import Vector
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

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
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

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
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

    must_have_skills: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, default=list)
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

    description_embedding: Mapped[list[float] | None] = mapped_column(Vector(1024), nullable=True)

    canonical_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("postings.id", ondelete="SET NULL"),
        nullable=True,
    )

    def __repr__(self) -> str:
        return f"<Posting company={self.company!r} title={self.title!r}>"


class Profile(Base):
    """Single-row table holding the user's resume and targeting preferences."""

    __tablename__ = "profile"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    resume_text: Mapped[str] = mapped_column(Text, nullable=False)

    target_yoe_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    target_yoe_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    target_locations: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, default=list)
    remote_ok: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    must_have_skills: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, default=list)
    nice_to_have_skills: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, default=list
    )
    excluded_keywords: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, default=list)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<Profile id={self.id} resume_len={len(self.resume_text)}>"


class RelevanceScore(Base):
    """Output of the LLM relevance scorer for one parsed posting."""

    __tablename__ = "relevance_scores"

    posting_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("postings.id", ondelete="CASCADE"),
        primary_key=True,
    )

    score: Mapped[float] = mapped_column(Float, nullable=False)
    reasoning: Mapped[str] = mapped_column(Text, nullable=False)

    skills_matched: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, default=list)
    skills_missing: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, default=list)

    yoe_match: Mapped[bool] = mapped_column(Boolean, nullable=False)
    location_match: Mapped[bool] = mapped_column(Boolean, nullable=False)

    hard_blockers: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, default=list)
    one_line_summary: Mapped[str] = mapped_column(Text, nullable=False)

    scored_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<RelevanceScore posting_id={self.posting_id} score={self.score:.2f}>"


class Digest(Base):
    """One row per digest sent. posting_ids tracks what was included."""

    __tablename__ = "digests"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    posting_ids: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(UUID(as_uuid=True)), nullable=False)
    delivery_method: Mapped[str] = mapped_column(String(32), nullable=False)
    delivery_status: Mapped[str] = mapped_column(String(32), nullable=False)
    delivery_message_id: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<Digest sent_at={self.sent_at} n_items={len(self.posting_ids)}>"
