import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.database import async_session
from app.services.polymarket import PolymarketClient
from app.services.resolution import resolve_events

logger = logging.getLogger("cortex.scheduler")


def create_scheduler() -> AsyncIOScheduler:
    """Create an AsyncIOScheduler instance (APScheduler 3.11.x)."""
    return AsyncIOScheduler()


async def resolution_job(poly_client: PolymarketClient) -> None:
    """Scheduled job: resolve closed events and calculate Brier Scores."""
    logger.info("Running scheduled resolution job...")
    try:
        async with async_session() as session:
            await resolve_events(poly_client, session)
    except Exception:
        logger.exception("Resolution job failed")
        raise
