"""ApplyTrak FastAPI application.

Run locally:
    uvicorn applytrak.api.main:app --reload --port 8000

Docs auto-generated at:
    http://localhost:8000/docs       (Swagger UI)
    http://localhost:8000/redoc      (ReDoc)
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import APIRouter, FastAPI

from applytrak.api.demo import router as demo_router
from applytrak.api.scheduler import make_scheduler
from applytrak.config import settings
from applytrak.pipeline import (
    DEFAULT_FETCH_LIMIT,
    DedupResult,
    DigestResult,
    EmbedResult,
    FetchResult,
    ParseResult,
    PipelineRunResult,
    ScoreResult,
    run_all,
    run_dedup,
    run_digest,
    run_embed,
    run_fetch,
    run_parse,
    run_score,
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Start the scheduler on app startup; shut it down on app exit."""
    scheduler: AsyncIOScheduler | None = None
    if settings.run_scheduler:
        scheduler = make_scheduler()
        scheduler.start()
        for job in scheduler.get_jobs():
            logger.info("[scheduler] job=%s next_run=%s", job.id, job.next_run_time)
        app.state.scheduler = scheduler
    else:
        logger.info("[scheduler] disabled (RUN_SCHEDULER=false)")
        app.state.scheduler = None

    yield

    if scheduler is not None:
        scheduler.shutdown(wait=False)
        logger.info("[scheduler] shut down")


app = FastAPI(
    title="ApplyTrak",
    description=(
        "Paste a resume, get ranked job matches from Hacker News hiring threads. "
        "Postings are fetched, parsed, and embedded on a schedule; matching is "
        "pgvector search followed by LLM scoring against the resume."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(demo_router)


@app.get("/health", tags=["meta"])
def health() -> dict:
    """Liveness probe. Returns 200 OK as long as the process is up."""
    return {"status": "ok"}


@app.get("/scheduler/jobs", tags=["meta"])
def scheduler_jobs() -> list[dict]:
    """List currently-scheduled jobs and their next run times.

    Returns an empty list when RUN_SCHEDULER=false.
    """
    scheduler: AsyncIOScheduler | None = getattr(app.state, "scheduler", None)
    if scheduler is None:
        return []
    return [
        {
            "id": job.id,
            "name": job.name,
            "trigger": str(job.trigger),
            "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
        }
        for job in scheduler.get_jobs()
    ]


@app.get("/info", tags=["meta"])
def info() -> dict:
    """Service metadata: model versions, thresholds, intervals.

    Useful for confirming a deploy picked up the env vars you expected.
    """
    return {
        "service": "applytrak",
        "version": app.version,
        "models": {
            "parse": settings.anthropic_model_parse,
            "score": settings.anthropic_model_score,
            "embedding": settings.embedding_model,
        },
        "thresholds": {
            "relevance": settings.relevance_threshold,
            "dedupe_similarity": settings.dedupe_similarity_threshold,
        },
        "fetch_interval_hours": settings.fetch_interval_hours,
        "digest_max_items": settings.digest_max_items,
    }


# ---------------------------------------------------------------------------
# Pipeline trigger endpoints
#
# Each calls the same function the corresponding script calls. They block the
# HTTP request for the duration of the run — fine for personal/admin use; in
# production you'd return immediately and run the work in a background task.
#
# Mounted only when EXPOSE_ADMIN_ENDPOINTS is true. The public demo runs with it
# off so visitors can't trigger pipeline work (which spends API quota).
# ---------------------------------------------------------------------------

admin_router = APIRouter(prefix="/run", tags=["pipeline"])


@admin_router.post("/fetch")
def trigger_fetch(limit: int = DEFAULT_FETCH_LIMIT) -> FetchResult:
    """Fetch latest HN 'Who is hiring?' comments → raw_postings."""
    return run_fetch(limit=limit)


@admin_router.post("/parse")
def trigger_parse() -> ParseResult:
    """Parse all unparsed raw_postings → postings."""
    return run_parse()


@admin_router.post("/embed")
def trigger_embed() -> EmbedResult:
    """Embed all postings missing (or holding a stale) description_embedding."""
    return run_embed()


@admin_router.post("/dedup")
def trigger_dedup() -> DedupResult:
    """Mark duplicate postings via pgvector cosine similarity."""
    return run_dedup()


@admin_router.post("/score")
def trigger_score() -> ScoreResult:
    """Score all unscored canonical postings against the stored profile."""
    return run_score()


@admin_router.post("/all")
def trigger_all(fetch_limit: int = DEFAULT_FETCH_LIMIT) -> PipelineRunResult:
    """Run the entire pipeline end-to-end (fetch → parse → embed → dedup → score)."""
    return run_all(fetch_limit=fetch_limit)


@admin_router.post("/digest")
def trigger_digest(include_sent: bool = False) -> DigestResult:
    """Build, send, and record the daily digest.

    Pass ?include_sent=true to ignore the de-dup table (for previewing).
    """
    return run_digest(exclude_sent=not include_sent)


if settings.expose_admin_endpoints:
    app.include_router(admin_router)
else:
    logger.info("[api] admin /run/* endpoints disabled (EXPOSE_ADMIN_ENDPOINTS=false)")
