"""One-time script to truncate all events from the database."""
import asyncio
import logging

from sqlalchemy import text

from app.database import async_session

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("cortex.truncate")


async def main():
    async with async_session() as session:
        result = await session.execute(text("SELECT COUNT(*) FROM events"))
        count = result.scalar()
        logger.info("Found %d events to delete", count)

        await session.execute(text("TRUNCATE TABLE events CASCADE"))
        await session.commit()
        logger.info("All events truncated")


if __name__ == "__main__":
    asyncio.run(main())
