"""Public demo: paste a resume, get ranked job matches.

Two-stage retrieve-then-rerank, split across two endpoints so every request
stays short (serverless duration limits) and the UI can fill in progressively:

  POST /api/match  → extract targeting from the resume (1 LLM call), embed it
                     (1 call), pgvector-search the corpus, return top-K candidates
  POST /api/score  → score ONE candidate against the resume (1 LLM call)

The browser calls /api/match once, then /api/score per candidate with small
concurrency. Nothing about a visitor is ever persisted.

Abuse posture: resume length cap, top-K cap, and the provider rate limiter.
The LLM free-tier daily quota is the real backstop — exhausting it degrades to
a friendly error rather than a bill.
"""

import logging
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from applytrak.config import settings
from applytrak.db import session_scope
from applytrak.llm.embeddings import current_embedding_model, embed_text
from applytrak.llm.profile_prompt import extract_profile, to_profile_config
from applytrak.llm.score_prompt import score_posting
from applytrak.models import Posting, RawPosting
from applytrak.schemas import ExtractedProfile, ParsedJD, RelevanceJudgment

logger = logging.getLogger(__name__)

router = APIRouter()

templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

LATEST_POSTINGS_LIMIT = 12


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class MatchRequest(BaseModel):
    resume_text: str = Field(min_length=100)


class Candidate(BaseModel):
    posting_id: uuid.UUID
    company: str
    title: str
    location: str | None
    is_remote: bool
    url: str
    similarity: float


class MatchResponse(BaseModel):
    profile: ExtractedProfile
    candidates: list[Candidate]
    corpus_size: int


class ScoreRequest(BaseModel):
    resume_text: str = Field(min_length=100)
    profile: ExtractedProfile
    posting_id: uuid.UUID


class ScoreResponse(BaseModel):
    posting_id: uuid.UUID
    judgment: RelevanceJudgment


class PostingSummary(BaseModel):
    company: str
    title: str
    location: str | None
    is_remote: bool
    url: str


class Stats(BaseModel):
    postings: int
    companies: int
    last_fetched_at: datetime | None


# ---------------------------------------------------------------------------
# Landing page
# ---------------------------------------------------------------------------


@router.get("/", response_class=HTMLResponse, include_in_schema=False)
def landing(request: Request) -> HTMLResponse:
    """Render the matcher page with corpus stats and a sample of recent postings."""
    with session_scope() as session:
        stats = _load_stats(session)
        latest = _load_latest_postings(session)

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "stats": stats,
            "latest": latest,
            "resume_max_chars": settings.demo_resume_max_chars,
            "top_k": settings.match_top_k,
        },
    )


@router.get("/api/stats", tags=["demo"])
def get_stats() -> Stats:
    """Corpus size and freshness."""
    with session_scope() as session:
        return _load_stats(session)


# ---------------------------------------------------------------------------
# Match flow
# ---------------------------------------------------------------------------


@router.post("/api/match", tags=["demo"])
def match(payload: MatchRequest) -> MatchResponse:
    """Stage 1: read the resume, then vector-search the corpus for candidates.

    Cheap and fast — no per-posting LLM calls happen here.
    """
    resume_text = _validated_resume(payload.resume_text)

    try:
        extracted = extract_profile(resume_text)
    except Exception as e:
        raise _llm_error(e, "reading your resume") from e

    try:
        resume_vector = embed_text(resume_text, input_type="query")
    except Exception as e:
        raise _llm_error(e, "embedding your resume") from e

    tag = current_embedding_model()
    cutoff = datetime.now(UTC) - timedelta(days=settings.match_recent_days)

    with session_scope() as session:
        corpus_size = _count_searchable(session, tag=tag, cutoff=cutoff)
        if corpus_size == 0:
            raise HTTPException(
                status_code=503,
                detail=(
                    "No job postings are available yet. The pipeline populates them "
                    "on a schedule — check back shortly."
                ),
            )

        distance = Posting.description_embedding.cosine_distance(resume_vector)
        rows = session.execute(
            select(
                Posting.id,
                Posting.company,
                Posting.title,
                Posting.location,
                Posting.is_remote,
                RawPosting.url,
                distance.label("dist"),
            )
            .join(RawPosting, Posting.raw_posting_id == RawPosting.id)
            .where(_searchable(tag=tag, cutoff=cutoff))
            .order_by(distance)
            .limit(settings.match_top_k)
        ).all()

    candidates = [
        Candidate(
            posting_id=row.id,
            company=row.company,
            title=row.title,
            location=row.location,
            is_remote=row.is_remote,
            url=row.url,
            similarity=round(1.0 - float(row.dist), 4),
        )
        for row in rows
    ]
    logger.info(
        "match: resume_len=%d corpus=%d candidates=%d",
        len(resume_text),
        corpus_size,
        len(candidates),
    )
    return MatchResponse(profile=extracted, candidates=candidates, corpus_size=corpus_size)


@router.post("/api/score", tags=["demo"])
def score(payload: ScoreRequest) -> ScoreResponse:
    """Stage 2: score one candidate posting against the resume.

    One LLM call per request. The browser fans these out over the candidates
    returned by /api/match so results can render as they arrive.
    """
    resume_text = _validated_resume(payload.resume_text)
    profile = to_profile_config(resume_text, payload.profile)

    with session_scope() as session:
        posting = session.get(Posting, payload.posting_id)
        if posting is None:
            raise HTTPException(status_code=404, detail="Posting not found.")
        parsed = ParsedJD.model_validate(posting, from_attributes=True)

    try:
        judgment = score_posting(parsed, profile)
    except Exception as e:
        raise _llm_error(e, "scoring this posting") from e

    return ScoreResponse(posting_id=payload.posting_id, judgment=judgment)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _validated_resume(resume_text: str) -> str:
    text = resume_text.strip()
    if len(text) > settings.demo_resume_max_chars:
        raise HTTPException(
            status_code=413,
            detail=(
                f"Resume is too long ({len(text)} chars). "
                f"Please trim it to {settings.demo_resume_max_chars} characters or fewer."
            ),
        )
    return text


def _llm_error(exc: Exception, doing: str) -> HTTPException:
    """Map provider failures to a 503 the page can show verbatim.

    Free-tier quota exhaustion is the expected failure here, so it gets its own
    message instead of a generic error.
    """
    message = str(exc)
    quota_hit = any(
        marker in message.lower() for marker in ("quota", "429", "resource_exhausted", "rate limit")
    )
    logger.warning("demo LLM failure while %s: %s: %s", doing, type(exc).__name__, exc)
    if quota_hit:
        detail = (
            "The demo has used up its free AI quota for now. "
            "It resets daily — please try again later."
        )
    else:
        detail = f"Something went wrong while {doing}. Please try again."
    return HTTPException(status_code=503, detail=detail)


def _published_at():
    """When the posting went live, falling back to ingest time for older rows."""
    return func.coalesce(RawPosting.posted_at, RawPosting.fetched_at)


def _searchable(*, tag: str, cutoff: datetime):
    """Filter for postings eligible as match candidates.

    Canonical only (no duplicates), embedded with the active model (vectors from
    other models are not comparable), and recent enough to still be open.
    """
    return (
        (Posting.canonical_id.is_(None))
        & (Posting.description_embedding.is_not(None))
        & (Posting.embedding_model == tag)
        & (_published_at() >= cutoff)
    )


def _count_searchable(session, *, tag: str, cutoff: datetime) -> int:
    return (
        session.execute(
            select(func.count())
            .select_from(Posting)
            .join(RawPosting, Posting.raw_posting_id == RawPosting.id)
            .where(_searchable(tag=tag, cutoff=cutoff))
        ).scalar_one()
        or 0
    )


def _load_stats(session) -> Stats:
    row = session.execute(
        select(
            func.count(Posting.id),
            func.count(func.distinct(Posting.company)),
            func.max(_published_at()),
        )
        .select_from(Posting)
        .join(RawPosting, Posting.raw_posting_id == RawPosting.id)
        .where(Posting.canonical_id.is_(None))
    ).one()
    return Stats(postings=row[0] or 0, companies=row[1] or 0, last_fetched_at=row[2])


def _load_latest_postings(session) -> list[PostingSummary]:
    rows = session.execute(
        select(
            Posting.company,
            Posting.title,
            Posting.location,
            Posting.is_remote,
            RawPosting.url,
        )
        .join(RawPosting, Posting.raw_posting_id == RawPosting.id)
        .where(Posting.canonical_id.is_(None))
        .order_by(_published_at().desc())
        .limit(LATEST_POSTINGS_LIMIT)
    ).all()
    return [
        PostingSummary(
            company=row.company,
            title=row.title,
            location=row.location,
            is_remote=row.is_remote,
            url=row.url,
        )
        for row in rows
    ]
