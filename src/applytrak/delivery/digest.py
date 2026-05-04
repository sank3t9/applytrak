"""Build and send the daily digest.

Public API:
    select_top_postings(session, ...) -> list[DigestRow]
    build_digest_message(rows) -> str
    record_digest_sent(session, ...) -> Digest
"""

import html
import logging
import uuid
from datetime import datetime

from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from applytrak.config import settings
from applytrak.models import Digest, Posting, RawPosting, RelevanceScore

logger = logging.getLogger(__name__)


class DigestRow(BaseModel):
    """One entry in the digest. Plain Pydantic so it survives session close."""

    posting_id: uuid.UUID
    company: str
    title: str
    location: str | None
    url: str
    score: float
    one_line_summary: str


def select_top_postings(
    session: Session,
    *,
    max_items: int | None = None,
    min_score: float | None = None,
    exclude_sent: bool = True,
) -> list[DigestRow]:
    """Top canonical postings without hard_blockers.

    `exclude_sent=True` filters out postings already included in any prior digest.
    Pass False to preview the same postings repeatedly (e.g., for testing).
    """
    max_items = max_items if max_items is not None else settings.digest_max_items
    min_score = min_score if min_score is not None else settings.relevance_threshold

    stmt = (
        select(
            Posting.id,
            Posting.company,
            Posting.title,
            Posting.location,
            RawPosting.url,
            RelevanceScore.score,
            RelevanceScore.one_line_summary,
        )
        .join(RelevanceScore, Posting.id == RelevanceScore.posting_id)
        .join(RawPosting, Posting.raw_posting_id == RawPosting.id)
        .where(Posting.canonical_id.is_(None))
        .where(RelevanceScore.score >= min_score)
        .where(func.cardinality(RelevanceScore.hard_blockers) == 0)
        .order_by(RelevanceScore.score.desc())
        .limit(max_items)
    )

    if exclude_sent:
        sent_postings = select(func.unnest(Digest.posting_ids))
        stmt = stmt.where(~Posting.id.in_(sent_postings))

    return [
        DigestRow(
            posting_id=row.id,
            company=row.company,
            title=row.title,
            location=row.location,
            url=row.url,
            score=row.score,
            one_line_summary=row.one_line_summary,
        )
        for row in session.execute(stmt).all()
    ]


def record_digest_sent(
    session: Session,
    *,
    posting_ids: list[uuid.UUID],
    delivery_method: str,
    delivery_status: str,
    delivery_message_id: str | None = None,
) -> Digest:
    """Append a row to the digests table and flush so the id is populated."""
    digest = Digest(
        posting_ids=posting_ids,
        delivery_method=delivery_method,
        delivery_status=delivery_status,
        delivery_message_id=delivery_message_id,
    )
    session.add(digest)
    session.flush()
    return digest


def _h(text: str | None) -> str:
    """HTML-escape text for Telegram. Treats None as empty."""
    return html.escape(text or "")


def build_digest_message(rows: list[DigestRow]) -> str:
    """Format rows as a Telegram HTML message."""
    today = datetime.now().strftime("%B %d, %Y")
    lines: list[str] = [f"<b>🎯 ApplyTrak Digest</b> — {today}"]

    if not rows:
        lines.append("\n<i>No matches above threshold today.</i>")
        return "\n".join(lines)

    lines.append(f"<i>{len(rows)} match{'es' if len(rows) != 1 else ''}</i>")
    lines.append("")
    lines.append("─────────")
    lines.append("")

    for r in rows:
        location = _h(r.location) if r.location else "(location unspecified)"
        lines.append(f"⭐ <b>{r.score:.2f}</b> | <b>{_h(r.company)}</b> — {_h(r.title)}")
        lines.append(f"   📍 {location}")
        lines.append(f"   <i>{_h(r.one_line_summary)}</i>")
        lines.append(f'   🔗 <a href="{_h(r.url)}">View on HN</a>')
        lines.append("")

    return "\n".join(lines)
