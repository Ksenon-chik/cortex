import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.event import Event


@pytest.fixture
async def sample_events(db_session: AsyncSession):
    """Create sample events for testing."""
    events = [
        Event(
            polymarket_market_id=f"market-{i}",
            title=f"Test event {i}",
            description=f"Description {i}",
            category="politics" if i % 2 == 0 else "science",
            outcomes=["Yes", "No"],
            outcome_prices={"Yes": 0.5, "No": 0.5},
            active=True,
        )
        for i in range(5)
    ]
    db_session.add_all(events)
    await db_session.commit()
    for e in events:
        await db_session.refresh(e)
    return events


class TestListEvents:
    async def test_empty_response(self, client):
        resp = await client.get("/api/events")
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        assert data["total"] == 0
        assert data["page"] == 1
        assert data["page_size"] == 20
        assert data["has_next"] is False
        assert data["has_prev"] is False

    async def test_returns_paginated_events(self, client, sample_events):
        resp = await client.get("/api/events?page_size=2")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 2
        assert data["total"] == 5
        assert data["page"] == 1
        assert data["page_size"] == 2
        assert data["has_next"] is True
        assert data["has_prev"] is False

    async def test_category_filter(self, client, sample_events):
        resp = await client.get("/api/events?category=politics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3  # events 0, 2, 4 are politics
        for item in data["items"]:
            assert item["category"] == "politics"

    async def test_pagination_page_2(self, client, sample_events):
        resp = await client.get("/api/events?page=2&page_size=2")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 2
        assert data["page"] == 2
        assert data["has_prev"] is True

    async def test_invalid_page_size(self, client):
        resp = await client.get("/api/events?page_size=0")
        assert resp.status_code == 422

    async def test_page_size_capped(self, client):
        resp = await client.get("/api/events?page_size=101")
        assert resp.status_code == 422


class TestGetEvent:
    async def test_event_not_found(self, client):
        event_id = str(uuid.uuid4())
        resp = await client.get(f"/api/events/{event_id}")
        assert resp.status_code == 404

    async def test_invalid_uuid(self, client):
        resp = await client.get("/api/events/not-a-uuid")
        assert resp.status_code == 400

    async def test_get_existing_event(self, client, sample_events):
        event = sample_events[0]
        resp = await client.get(f"/api/events/{event.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == str(event.id)
        assert data["title"] == event.title
        assert data["category"] == event.category
