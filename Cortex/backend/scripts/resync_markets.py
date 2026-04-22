"""Force a full market sync from Polymarket."""
import asyncio
import logging

from app.database import async_session
from app.services.polymarket import PolymarketClient
from app.services.sync import sync_markets
from app.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("cortex.resync")


async def main():
    client = PolymarketClient(
        gamma_base_url=settings.polymarket_gamma_api_url,
        clob_base_url=settings.polymarket_clob_api_url,
    )
    try:
        count = await sync_markets(client, async_session())
        logger.info("Resync complete: %d markets synced", count)
    finally:
        await client.aclose()


if __name__ == "__main__":
    asyncio.run(main())
