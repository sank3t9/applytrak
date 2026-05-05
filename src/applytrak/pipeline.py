"""Pipeline orchestration.

Each `run_*` function returns a typed result and never prints. It's called from:
  - scripts/*.py (which add a print + sys.exit wrapper)
  - api/main.py trigger endpoints (which return the result as JSON)
  - api/scheduler.py (Phase 5.3) (which logs the result)
"""

import logging
import time

import httpx
from pydantic import BaseModel
from sqlalchemy import select

from applytrak.config import settings
from applytrak.db import session_scope
from applytrak.delivery.digest import (
    build_digest_message,
    record_digest_sent,
    select_top_postings,
)
from applytrak.delivery.telegram import send_message
from applytrak.llm.embeddings import embed_texts
from applytrak.llm.parse_prompt import parse_jd
from applytrak.llm.score_prompt import score_posting
from applytrak.models import Posting, Profile, RawPosting
from applytrak.profile_config import ProfileConfig
from applytrak.schemas import ParsedJD
from applytrak.services.postings import fetch_unparsed_raw_postings, save_posting
from applytrak.services.raw_postings import save_raw_posting
from applytrak.services.scores import fetch_unscored_postings, save_score
from applytrak.sources.hn import (
    fetch_comment,
    get_latest_who_is_hiring_thread_id,
    get_top_level_comment_ids,
)

logger = logging.getLogger(__name__)

DEFAULT_FETCH_LIMIT = 30
EMBED_BATCH_SIZE = 16
HN_FETCH_SLEEP_S = 0.1


# ---------------------------------------------------------------------------
# Result schemas (typed return values from each pipeline stage)
# ---------------------------------------------------------------------------


class FetchResult(BaseModel):
    thread_id: int | None = None
    inserted: int = 0
    skipped: int = 0
    empty_or_deleted: int = 0
    failed: int = 0


class ParseResult(BaseModel):
    inserted: int = 0
    skipped: int = 0
    failed: int = 0


class EmbedResult(BaseModel):
    embedded: int = 0
    failed: int = 0
    batches: int = 0


class DedupResult(BaseModel):
    threshold: float
    canonicals_kept: int = 0
    marked_as_duplicate: int = 0
    already_resolved: int = 0


class ScoreResult(BaseModel):
    inserted: int = 0
    skipped: int = 0
    failed: int = 0


class DigestResult(BaseModel):
    sent: bool
    n_items: int
    delivery_status: str
    digest_id: str | None = None
    delivery_message_id: str | None = None


class PipelineRunResult(BaseModel):
    fetch: FetchResult
    parse: ParseResult
    embed: EmbedResult
    dedup: DedupResult
    score: ScoreResult


# ---------------------------------------------------------------------------
# Stage functions
# ---------------------------------------------------------------------------


def run_fetch(limit: int = DEFAULT_FETCH_LIMIT) -> FetchResult:
    """Fetch top-N comments from latest 'Who is hiring?' thread → raw_postings."""
    with httpx.Client(timeout=10.0) as client:
        thread_id = get_latest_who_is_hiring_thread_id(client)
        if thread_id is None:
            return FetchResult()

        all_ids = get_top_level_comment_ids(client, thread_id)
        targets = all_ids[:limit]
        result = FetchResult(thread_id=thread_id)

        for cid in targets:
            try:
                posting = fetch_comment(client, cid)
            except Exception as e:
                logger.warning("fetch_comment(%s) failed: %s: %s", cid, type(e).__name__, e)
                result.failed += 1
                continue

            if posting is None:
                result.empty_or_deleted += 1
                continue

            with session_scope() as session:
                _, created = save_raw_posting(session, posting)
                if created:
                    result.inserted += 1
                else:
                    result.skipped += 1

            time.sleep(HN_FETCH_SLEEP_S)

        return result


def run_parse() -> ParseResult:
    """Parse all unparsed raw_postings → postings via Claude Haiku."""
    with session_scope() as session:
        unparsed = fetch_unparsed_raw_postings(session)
        targets = [(r.id, r.raw_text) for r in unparsed]

    result = ParseResult()
    for raw_id, raw_text in targets:
        try:
            parsed = parse_jd(raw_text)
        except Exception as e:
            logger.warning("parse_jd(raw_id=%s) failed: %s: %s", raw_id, type(e).__name__, e)
            result.failed += 1
            continue

        with session_scope() as session:
            _, created = save_posting(session, raw_id, parsed)
            if created:
                result.inserted += 1
            else:
                result.skipped += 1

    return result


def run_embed() -> EmbedResult:
    """Embed all postings missing description_embedding via Voyage AI."""
    with session_scope() as session:
        rows = list(
            session.execute(
                select(Posting.id, RawPosting.raw_text)
                .join(RawPosting, Posting.raw_posting_id == RawPosting.id)
                .where(Posting.description_embedding.is_(None))
                .order_by(Posting.parsed_at)
            ).all()
        )

    result = EmbedResult()
    for start in range(0, len(rows), EMBED_BATCH_SIZE):
        batch = rows[start : start + EMBED_BATCH_SIZE]
        ids = [row[0] for row in batch]
        texts = [row[1] for row in batch]

        try:
            vectors = embed_texts(texts)
        except Exception as e:
            logger.warning("embed_texts batch failed: %s: %s", type(e).__name__, e)
            result.failed += len(batch)
            continue

        with session_scope() as session:
            for posting_id, vec in zip(ids, vectors, strict=True):
                p = session.get(Posting, posting_id)
                if p is not None:
                    p.description_embedding = vec
                    result.embedded += 1

        result.batches += 1

    return result


def run_dedup() -> DedupResult:
    """Mark duplicate postings via pgvector cosine similarity."""
    threshold = settings.dedupe_similarity_threshold
    result = DedupResult(threshold=threshold)

    with session_scope() as session:
        all_postings = list(
            session.scalars(
                select(Posting)
                .where(Posting.description_embedding.is_not(None))
                .order_by(Posting.parsed_at)
            )
        )

        for posting in all_postings:
            if posting.canonical_id is not None:
                result.already_resolved += 1
                continue

            distance_expr = Posting.description_embedding.cosine_distance(
                posting.description_embedding
            )
            row = session.execute(
                select(Posting.id, distance_expr.label("dist"))
                .where(Posting.description_embedding.is_not(None))
                .where(Posting.canonical_id.is_(None))
                .where(Posting.id != posting.id)
                .where(Posting.parsed_at < posting.parsed_at)
                .order_by(distance_expr)
                .limit(1)
            ).first()

            if row is None:
                result.canonicals_kept += 1
                continue

            similarity = 1.0 - float(row.dist)

            if similarity >= threshold:
                posting.canonical_id = row.id
                session.flush()
                result.marked_as_duplicate += 1
            else:
                result.canonicals_kept += 1

    return result


def run_score() -> ScoreResult:
    """Score all unscored canonical postings via Claude Sonnet."""
    with session_scope() as session:
        profile = session.get(Profile, 1)
        if profile is None:
            raise RuntimeError("No profile in DB. Run scripts/seed_profile.py first.")
        profile_cfg = ProfileConfig.model_validate(profile, from_attributes=True)

        unscored = fetch_unscored_postings(session)
        targets = [(p.id, ParsedJD.model_validate(p, from_attributes=True)) for p in unscored]

    result = ScoreResult()
    for posting_id, parsed_jd in targets:
        try:
            judgment = score_posting(parsed_jd, profile_cfg)
        except Exception as e:
            logger.warning(
                "score_posting(posting_id=%s) failed: %s: %s",
                posting_id,
                type(e).__name__,
                e,
            )
            result.failed += 1
            continue

        with session_scope() as session:
            _, created = save_score(session, posting_id, judgment)
            if created:
                result.inserted += 1
            else:
                result.skipped += 1

    return result


def run_all(fetch_limit: int = DEFAULT_FETCH_LIMIT) -> PipelineRunResult:
    """Run the entire pipeline end-to-end. Used by the scheduler in 5.3."""
    return PipelineRunResult(
        fetch=run_fetch(fetch_limit),
        parse=run_parse(),
        embed=run_embed(),
        dedup=run_dedup(),
        score=run_score(),
    )


def run_digest(*, exclude_sent: bool = True) -> DigestResult:
    """Build, send to Telegram, and record today's digest.

    Idempotent (with exclude_sent=True): re-runs skip already-sent postings.
    On Telegram failure, still records a row with delivery_status='failed' so
    failed posting_ids aren't re-attempted in the next run — flip exclude_sent
    to False to retry.
    """
    with session_scope() as session:
        rows = select_top_postings(session, exclude_sent=exclude_sent)

    if not rows:
        logger.info("[digest] no new postings to send")
        return DigestResult(sent=False, n_items=0, delivery_status="no_items")

    message = build_digest_message(rows)

    try:
        response = send_message(message)
        msg_id = response.get("result", {}).get("message_id")
        delivery_message_id = str(msg_id) if msg_id is not None else None
        status = "sent"
        logger.info("[digest] sent %d items (telegram message_id=%s)", len(rows), msg_id)
    except Exception as e:
        logger.warning("[digest] telegram send failed: %s: %s", type(e).__name__, e)
        delivery_message_id = None
        status = "failed"

    with session_scope() as session:
        digest = record_digest_sent(
            session,
            posting_ids=[r.posting_id for r in rows],
            delivery_method="telegram",
            delivery_status=status,
            delivery_message_id=delivery_message_id,
        )
        digest_id = str(digest.id)

    return DigestResult(
        sent=(status == "sent"),
        n_items=len(rows),
        delivery_status=status,
        digest_id=digest_id,
        delivery_message_id=delivery_message_id,
    )
