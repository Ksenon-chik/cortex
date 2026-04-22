import json
import logging
from datetime import datetime, timezone

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants.categories import detect_category
from app.models.event import Event
from app.schemas.polymarket import GammaMarket
from app.services.polymarket import PolymarketClient

logger = logging.getLogger("cortex.sync")


def _parse_list_field(value, default=None):
    """Parse a field that may be a JSON string or a real list."""
    if value is None:
        return default or []
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (json.JSONDecodeError, ValueError):
            return default or []
    return value


def gamma_market_to_event(market: GammaMarket) -> dict:
    """Map a GammaMarket response to Event model fields with strict TZ handling."""
    outcomes = _parse_list_field(market.outcomes)
    raw_prices = _parse_list_field(market.outcome_prices)

    # Создаем словарь цен, защищенный от пустых списков
    outcome_prices = {}
    if outcomes and raw_prices:
        outcome_prices = dict(zip(outcomes, raw_prices, strict=False))

    end_date = None
    if market.end_date:
        try:
            dt = market.end_date
            # Если Pydantic еще не сконвертировал строку в datetime
            if isinstance(dt, str):
                # Убираем 'Z' и парсим как UTC
                dt = datetime.fromisoformat(dt.replace("Z", "+00:00"))

            # Ключевой момент: приводим к UTC и УДАЛЯЕМ tzinfo (делаем naive)
            # Это решает ошибку: can't subtract offset-naive and offset-aware datetimes
            if dt.tzinfo is not None:
                end_date = dt.astimezone(timezone.utc).replace(tzinfo=None)
            else:
                end_date = dt
        except Exception as e:
            logger.warning("Could not parse end_date for market %s: %s", market.id, e)

    norm_cat = detect_category(market.question, market.description or "")

    return {
        "polymarket_market_id": market.id,
        "title": market.question,
        "description": market.description or None,
        "category": norm_cat,
        "category_normalized": norm_cat,
        "outcomes": outcomes,
        "outcome_prices": outcome_prices,
        "active": market.active,
        "closed": market.closed,
        "end_date": end_date,
    }


async def sync_markets(poly_client: PolymarketClient, session: AsyncSession) -> int:
    """Fetch active markets from Polymarket and upsert into local DB."""
    logger.info("Fetching active markets from Polymarket...")
    try:
        markets = await poly_client.fetch_active_markets()
    except Exception as e:
        logger.error("Failed to fetch markets from API: %s", e)
        return 0

    if not markets:
        logger.warning("No markets fetched from Polymarket")
        return 0

    logger.info("Upserting %d markets...", len(markets))

    synced_count = 0
    for market in markets:
        try:
            event_data = gamma_market_to_event(market)
            stmt = insert(Event).values(**event_data)
            stmt = stmt.on_conflict_do_update(
                index_elements=["polymarket_market_id"],
                set_={
                    "title": stmt.excluded.title,
                    "description": stmt.excluded.description,
                    "category": stmt.excluded.category,
                    "category_normalized": stmt.excluded.category_normalized,
                    "outcomes": stmt.excluded.outcomes,
                    "outcome_prices": stmt.excluded.outcome_prices,
                    "active": stmt.excluded.active,
                    "closed": stmt.excluded.closed,
                    "end_date": stmt.excluded.end_date,
                    "updated_at": func.now(),
                },
            )
            await session.execute(stmt)
            synced_count += 1
        except Exception as e:
            logger.error("Error upserting market %s: %s", market.id, e)
            # Продолжаем цикл, чтобы один битый маркет не ломал всё
            continue

    await session.commit()
    logger.info("Successfully synced %d markets", synced_count)
    return synced_count