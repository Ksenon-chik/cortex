from unittest.mock import AsyncMock, MagicMock, patch
import os

import httpx
import pytest

# Remove proxy env vars that httpx reads and can't handle
_PROXY_VARS = (
    "ALL_PROXY", "all_proxy", "HTTP_PROXY", "HTTPS_PROXY",
    "http_proxy", "https_proxy", "FTP_PROXY", "ftp_proxy",
    "NO_PROXY", "no_proxy",
)
for _v in _PROXY_VARS:
    os.environ.pop(_v, None)

from app.schemas.polymarket import ClobPrice, GammaEvent, GammaMarket
from app.services.polymarket import PolymarketClient
from app.services.sync import gamma_market_to_event

MARKET_FIXTURE = {
    "id": "m1",
    "question": "Q?",
    "outcomes": ["Yes", "No"],
    "outcomePrices": [0.5, 0.5],
}


class TestGammaMarketModel:
    def test_parses_valid_market(self):
        market = GammaMarket.model_validate({
            "id": "market-123",
            "question": "Will X happen?",
            "description": "Some description",
            "category": "politics",
            "outcomes": ["Yes", "No"],
            "outcomePrices": [0.6, 0.4],
            "active": True,
            "closed": False,
        })
        assert market.id == "market-123"
        assert market.question == "Will X happen?"
        assert market.outcomes == ["Yes", "No"]
        assert market.outcome_prices == [0.6, 0.4]
        assert market.active is True

    def test_ignores_extra_fields(self):
        market = GammaMarket.model_validate({
            "id": "market-456",
            "question": "Test?",
            "outcomes": ["Yes", "No"],
            "outcomePrices": [0.5, 0.5],
            "unknown_field": "should be ignored",
            "another_extra": 123,
        })
        assert market.id == "market-456"
        assert not hasattr(market, "unknown_field")

    def test_defaults_for_optional_fields(self):
        market = GammaMarket.model_validate({
            "id": "market-789",
            "question": "Minimal?",
        })
        assert market.description == ""
        assert market.category == ""
        assert market.outcomes == []
        assert market.active is True
        assert market.closed is False


class TestGammaEventModel:
    def test_parses_valid_event(self):
        event = GammaEvent.model_validate({
            "id": "event-123",
            "title": "Election 2026",
            "description": "US Election",
            "slug": "election-2026",
            "markets": [MARKET_FIXTURE],
        })
        assert event.id == "event-123"
        assert event.title == "Election 2026"
        assert len(event.markets) == 1
        assert event.markets[0].id == "m1"

    def test_parses_event_without_markets(self):
        event = GammaEvent.model_validate({
            "id": "event-456",
            "title": "Event without markets",
        })
        assert event.markets is None


class TestClobPriceModel:
    def test_parses_valid_price(self):
        price = ClobPrice.model_validate({
            "asset_id": "asset-123",
            "price": 0.65,
            "timestamp": "2026-01-01T00:00:00Z",
        })
        assert price.asset_id == "asset-123"
        assert price.price == 0.65
        assert price.timestamp == "2026-01-01T00:00:00Z"


class TestPolymarketClientParseMarkets:
    def test_parses_valid_markets(self):
        client = PolymarketClient(
            gamma_base_url="http://test",
            clob_base_url="http://test",
        )
        raw = [
            {
                "id": "m1", "question": "Q1?",
                "outcomes": ["Yes", "No"],
                "outcomePrices": [0.6, 0.4],
            },
            {
                "id": "m2", "question": "Q2?",
                "outcomes": ["Yes", "No"],
                "outcomePrices": [0.3, 0.7],
            },
        ]
        markets = client._parse_markets(raw)
        assert len(markets) == 2
        assert markets[0].id == "m1"
        assert markets[1].id == "m2"

    def test_skips_invalid_markets(self):
        client = PolymarketClient(
            gamma_base_url="http://test",
            clob_base_url="http://test",
        )
        raw = [
            {
                "id": "m1", "question": "Q1?",
                "outcomes": ["Yes", "No"],
                "outcomePrices": [0.6, 0.4],
            },
            {"id": "m2"},  # missing required "question" field
            {
                "id": "m3", "question": "Q3?",
                "outcomes": ["Yes", "No"],
                "outcomePrices": [0.5, 0.5],
            },
        ]
        markets = client._parse_markets(raw)
        assert len(markets) == 2
        assert markets[0].id == "m1"
        assert markets[1].id == "m3"

    def test_handles_empty_list(self):
        client = PolymarketClient(
            gamma_base_url="http://test",
            clob_base_url="http://test",
        )
        markets = client._parse_markets([])
        assert markets == []


class TestPolymarketClientBackoff:
    @pytest.mark.asyncio
    async def test_retries_on_429(self):
        """Test that the client retries and succeeds after a 429 response."""
        client = PolymarketClient(
            gamma_base_url="http://test",
            clob_base_url="http://test",
        )

        response_429 = MagicMock()
        response_429.status_code = 429
        response_429.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Rate limited", request=MagicMock(), response=response_429,
        )

        response_ok = MagicMock()
        response_ok.raise_for_status = MagicMock()
        response_ok.json.return_value = [MARKET_FIXTURE]

        mock_get = AsyncMock(side_effect=[
            httpx.HTTPStatusError(
                "Rate limited", request=MagicMock(), response=response_429,
            ),
            response_ok,
        ])

        mock_client = MagicMock()
        mock_client.get = mock_get

        with patch("app.services.polymarket.asyncio.sleep", new_callable=AsyncMock):
            result = await client._get(mock_client, "/markets", retries=3)

        assert mock_get.call_count == 2
        assert isinstance(result, list)
        assert result[0]["id"] == "m1"

    @pytest.mark.asyncio
    async def test_raises_after_max_retries_429(self):
        """Test that the client raises after exhausting retries on 429."""
        client = PolymarketClient(
            gamma_base_url="http://test",
            clob_base_url="http://test",
        )

        response_429 = MagicMock()
        response_429.status_code = 429

        err_429 = httpx.HTTPStatusError(
            "Rate limited", request=MagicMock(), response=response_429,
        )
        mock_get = AsyncMock(side_effect=[err_429, err_429, err_429])

        mock_client = MagicMock()
        mock_client.get = mock_get

        with patch("app.services.polymarket.asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(httpx.HTTPStatusError):
                await client._get(mock_client, "/markets", retries=3)

        assert mock_get.call_count == 3

    @pytest.mark.asyncio
    async def test_retries_on_500(self):
        """Test that the client retries on 500 server errors."""
        response_500 = MagicMock()
        response_500.status_code = 500

        response_ok = MagicMock()
        response_ok.raise_for_status = MagicMock()
        response_ok.json.return_value = [MARKET_FIXTURE]

        mock_get = AsyncMock(side_effect=[
            httpx.HTTPStatusError(
                "Server error", request=MagicMock(), response=response_500,
            ),
            response_ok,
        ])

        mock_client = MagicMock()
        mock_client.get = mock_get

        client = PolymarketClient(
            gamma_base_url="http://test",
            clob_base_url="http://test",
        )

        with patch("app.services.polymarket.asyncio.sleep", new_callable=AsyncMock):
            result = await client._get(mock_client, "/markets", retries=3)

        assert mock_get.call_count == 2
        assert result[0]["id"] == "m1"

    @pytest.mark.asyncio
    async def test_raises_immediately_on_404(self):
        """Test that 404 is not retried (not 429 or 500)."""
        response_404 = MagicMock()
        response_404.status_code = 404

        mock_get = AsyncMock(side_effect=[
            httpx.HTTPStatusError(
                "Not found", request=MagicMock(), response=response_404,
            ),
        ])

        mock_client = MagicMock()
        mock_client.get = mock_get

        client = PolymarketClient(
            gamma_base_url="http://test",
            clob_base_url="http://test",
        )

        with pytest.raises(httpx.HTTPStatusError):
            await client._get(mock_client, "/markets", retries=3)

        assert mock_get.call_count == 1


class TestGammaMarketToEvent:
    def test_maps_fields_correctly(self):
        market = GammaMarket.model_validate({
            "id": "market-abc",
            "question": "Will it rain?",
            "description": "Weather market",
            "category": "science",
            "outcomes": ["Yes", "No"],
            "outcomePrices": [0.3, 0.7],
            "active": True,
            "closed": False,
            "endDate": "2026-12-31T23:59:59Z",
        })
        event = gamma_market_to_event(market)
        assert event["polymarket_market_id"] == "market-abc"
        assert event["title"] == "Will it rain?"
        assert event["description"] == "Weather market"
        assert event["category"] == "science"
        assert event["outcomes"] == ["Yes", "No"]
        assert event["outcome_prices"] == {"Yes": 0.3, "No": 0.7}
        assert event["active"] is True
        assert event["closed"] is False
        assert event["end_date"] is not None

    def test_handles_empty_category(self):
        market = GammaMarket.model_validate({
            "id": "market-x",
            "question": "Q?",
        })
        event = gamma_market_to_event(market)
        assert event["category"] == "uncategorized"

    def test_handles_bad_end_date(self):
        market = GammaMarket.model_validate({
            "id": "market-y",
            "question": "Q?",
            "endDate": "not-a-date",
        })
        event = gamma_market_to_event(market)
        assert event["end_date"] is None

    def test_handles_missing_description(self):
        market = GammaMarket.model_validate({
            "id": "market-z",
            "question": "Q?",
        })
        event = gamma_market_to_event(market)
        assert event["description"] is None


class TestPolymarketClientCache:
    """Tests for the in-memory markets cache in search_markets."""

    def _make_market(self, idx: int) -> dict:
        return {
            "id": f"m{idx}",
            "question": f"Question {idx}?",
            "outcomes": ["Yes", "No"],
            "outcomePrices": [0.5, 0.5],
        }

    @pytest.mark.asyncio
    async def test_search_uses_cached_markets(self):
        """search_markets should use the cache, not re-fetch on every call."""
        client = PolymarketClient(
            gamma_base_url="http://test",
            clob_base_url="http://test",
        )

        markets_data = [self._make_market(i) for i in range(5)]
        call_count = 0

        async def counting_get(client_obj, path, params=None, retries=3):
            nonlocal call_count
            call_count += 1
            return markets_data

        with patch.object(client, "_get", counting_get):
            # First call — populates cache
            results, total = await client.search_markets(q="Question 1")
            assert total == 1  # only "Question 1?" matches in 0-4
            assert len(results) == 1
            assert results[0].id == "m1"
            assert call_count == 1  # one fetch

            # Second call — should use cache, no new fetches
            results2, total2 = await client.search_markets(q="Question 2")
            assert total2 == 1  # only "Question 2?" matches
            assert results2[0].id == "m2"
            assert call_count == 1  # still one fetch (cache hit)

    @pytest.mark.asyncio
    async def test_cache_invalidation(self):
        """clear_markets_cache should force a re-fetch on next search."""
        client = PolymarketClient(
            gamma_base_url="http://test",
            clob_base_url="http://test",
        )

        first_data = [self._make_market(i) for i in range(3)]
        second_data = [self._make_market(i) for i in range(3, 6)]

        call_sequence = []

        async def fake_get(client_obj, path, params=None, retries=3):
            call_sequence.append(params)
            if len(call_sequence) == 1:
                return first_data
            return second_data

        with patch.object(client, "_get", fake_get):
            # First search — populates cache
            results, total = await client.search_markets(q="")
            assert total == 3

            # Clear cache
            await client.clear_markets_cache()

            # Second search — must re-fetch
            results2, total2 = await client.search_markets(q="")
            assert total2 == 3
            assert results2[0].id == "m3"

        # Two fetches should have been made (first + after invalidation)
        assert len(call_sequence) == 2

    @pytest.mark.asyncio
    async def test_search_pagination(self):
        """search_markets should respect offset and limit."""
        client = PolymarketClient(
            gamma_base_url="http://test",
            clob_base_url="http://test",
        )

        markets_data = [self._make_market(i) for i in range(10)]

        with patch.object(client, "_get", return_value=markets_data):
            results, total = await client.search_markets(q="", limit=3, offset=0)
            assert total == 10
            assert len(results) == 3
            assert results[0].id == "m0"

            results2, _ = await client.search_markets(q="", limit=3, offset=3)
            assert len(results2) == 3
            assert results2[0].id == "m3"

            results3, _ = await client.search_markets(q="", limit=3, offset=9)
            assert len(results3) == 1
            assert results3[0].id == "m9"
