"""APScheduler setup. Started/stopped from the FastAPI lifespan."""

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from applytrak.config import settings
from applytrak.pipeline import run_all, run_digest

logger = logging.getLogger(__name__)


def _scheduled_pipeline_job() -> None:
    """Sync wrapper that runs the full pipeline and logs the result."""
    logger.info("[scheduler] starting full pipeline run")
    try:
        result = run_all()
        logger.info("[scheduler] pipeline run complete: %s", result.model_dump_json())
    except Exception:
        logger.exception("[scheduler] pipeline run failed")


def _scheduled_digest_job() -> None:
    """Sync wrapper that builds + sends the daily digest."""
    logger.info("[scheduler] starting daily digest")
    try:
        result = run_digest()
        logger.info("[scheduler] digest complete: %s", result.model_dump_json())
    except Exception:
        logger.exception("[scheduler] digest failed")


def make_scheduler() -> AsyncIOScheduler:
    """Build the scheduler with all jobs configured. Caller decides when to start it."""
    scheduler = AsyncIOScheduler()

    scheduler.add_job(
        _scheduled_pipeline_job,
        trigger=IntervalTrigger(hours=settings.fetch_interval_hours),
        id="pipeline",
        name="Full pipeline (fetch → parse → embed → dedup → score)",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )

    scheduler.add_job(
        _scheduled_digest_job,
        trigger=CronTrigger(hour=7, minute=0, timezone="America/New_York"),
        id="digest",
        name="Daily 7am Telegram digest",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )

    return scheduler
