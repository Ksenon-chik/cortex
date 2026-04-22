"""One-time script to backfill category_normalized for existing events."""
import asyncio
import logging

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants.categories import detect_category
from app.database import async_session
from app.models.event import Event

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("cortex.backfill")


async def main():
    async with async_session() as session:
        result = await session.execute(select(Event))
        events = result.scalars().all()

        logger.info("Found %d events to backfill", len(events))
        updated = 0

        for event in events:
            cat = detect_category(event.title, event.description or "")
            await session.execute(
                update(Event)
                .where(Event.id == event.id)
                .values(category=cat, category_normalized=cat)
            )
            updated += 1

        await session.commit()
        logger.info("Backfilled %d events with detected categories", updated)


if __name__ == "__main__":
    asyncio.run(main())
