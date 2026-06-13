"""Scheduler - Automated task scheduling for the T-Shirt Factory."""

import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.core.database import async_session
from app.tshirt_factory.orchestrator import Orchestrator
from app.tshirt_factory.config import tsf_settings

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


async def scheduled_full_pipeline():
    """Run the full pipeline on schedule."""
    logger.info("Scheduled pipeline run starting...")
    async with async_session() as db:
        orchestrator = Orchestrator(db)
        try:
            result = await orchestrator.run_full_pipeline()
            logger.info(f"Scheduled pipeline complete: {result.get('designs', {}).get('total_generated', 0)} designs generated")
        except Exception as e:
            logger.error(f"Scheduled pipeline failed: {e}")
        finally:
            await orchestrator.close()


async def scheduled_research():
    """Run research only on schedule."""
    logger.info("Scheduled research run starting...")
    async with async_session() as db:
        orchestrator = Orchestrator(db)
        try:
            result = await orchestrator.run_research_only()
            logger.info(f"Scheduled research complete: {result.get('total', 0)} items")
        except Exception as e:
            logger.error(f"Scheduled research failed: {e}")
        finally:
            await orchestrator.close()


async def scheduled_learning():
    """Run learning cycle on schedule."""
    logger.info("Scheduled learning cycle starting...")
    async with async_session() as db:
        from app.tshirt_factory.engines.learning import LearningEngine
        learning = LearningEngine(db)
        try:
            result = await learning.run_learning_cycle()
            logger.info(f"Scheduled learning complete: {result}")
        except Exception as e:
            logger.error(f"Scheduled learning failed: {e}")


def setup_tsf_scheduler():
    """Configure all scheduled jobs for the T-Shirt Factory."""

    # Full pipeline: runs daily at 4 AM
    scheduler.add_job(
        scheduled_full_pipeline,
        "cron",
        hour=4,
        minute=0,
        id="tsf_full_pipeline",
        replace_existing=True,
        misfire_grace_time=3600,
    )

    # Research: runs every N hours (configurable)
    scheduler.add_job(
        scheduled_research,
        "interval",
        hours=tsf_settings.RESEARCH_INTERVAL_HOURS,
        id="tsf_research",
        replace_existing=True,
        misfire_grace_time=1800,
    )

    # Learning cycle: runs every N hours (configurable)
    scheduler.add_job(
        scheduled_learning,
        "interval",
        hours=tsf_settings.LEARNING_UPDATE_INTERVAL_HOURS,
        id="tsf_learning",
        replace_existing=True,
        misfire_grace_time=1800,
    )

    scheduler.start()
    logger.info("T-Shirt Factory scheduler configured:")
    logger.info(f"  - Full pipeline: daily at 04:00")
    logger.info(f"  - Research: every {tsf_settings.RESEARCH_INTERVAL_HOURS}h")
    logger.info(f"  - Learning: every {tsf_settings.LEARNING_UPDATE_INTERVAL_HOURS}h")
