from unittest.mock import AsyncMock

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.event import Event
from app.schemas.polymarket import GammaMarket
from app.services.sync import sync_markets


def make_mock_market(overrides: dict | None = None) -> GammaMarket:
    """Create a test GammaMarket with defaults."""
    data = {
        "id": "test-market-1",
        "question": "Will it happen?",
        "description": "Test market",
        "category": "politics",
        "outcomes": ["Yes", "No"],
        "outcomePrices": [0.6, 0.4],
        "active": True,
        "closed": False,
    }
    if overrides:
        data.update(overrides)
    return GammaMarket.model_validate(data)


class TestSyncMarkets:
    @pytest.fixture
    def mock_client(self):
        client = AsyncMock()
        client.fetch_active_markets = AsyncMock(return_value=[])
        return client

    async def test_syncs_markets_to_db(self, mock_client, db_session: AsyncSession):
        markets = [make_mock_market({"id": "m1"}), make_mock_market({"id": "m2"})]
        mock_client.fetch_active_markets = AsyncMock(return_value=markets)

        count = await sync_markets(mock_client, db_session)
        assert count == 2

        result = await db_session.execute(select(Event))
        events = result.scalars().all()
        assert len(events) == 2
        assert events[0].polymarket_market_id == "m1"
        assert events[1].polymarket_market_id == "m2"

    async def test_upsert_no_duplicates(self, mock_client, db_session: AsyncSession):
        """Calling sync twice with same market doesn't duplicate."""
        market = make_mock_market({"id": "m1", "question": "Original"})
        mock_client.fetch_active_markets = AsyncMock(return_value=[market])

        await sync_markets(mock_client, db_session)
        await sync_markets(mock_client, db_session)

        result = await db_session.execute(select(func.count(Event.id)))
        count = result.scalar_one()
        assert count == 1

    async def test_upsert_updates_fields(self, mock_client, db_session: AsyncSession):
        """Second sync with changed data updates the record."""
        market = make_mock_market({"id": "m1", "question": "Original"})
        mock_client.fetch_active_markets = AsyncMock(return_value=[market])
        await sync_markets(mock_client, db_session)

        updated = make_mock_market({"id": "m1", "question": "Updated"})
        mock_client.fetch_active_markets = AsyncMock(return_value=[updated])
        await sync_markets(mock_client, db_session)

        stmt = select(Event).where(Event.polymarket_market_id == "m1")
        result = await db_session.execute(stmt)
        event = result.scalar_one()
        assert event.title == "Updated"

    async def test_empty_market_list(self, mock_client, db_session: AsyncSession):
        mock_client.fetch_active_markets = AsyncMock(return_value=[])
        count = await sync_markets(mock_client, db_session)
        assert count == 0
