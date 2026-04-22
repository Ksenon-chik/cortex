import asyncio
import logging
import time

import httpx

from app.schemas.polymarket import ClobPrice, GammaMarket

logger = logging.getLogger("cortex.polymarket")


class PolymarketClient:
    """Async client for Polymarket Gamma API and CLOB API with exponential backoff."""

    def __init__(self, gamma_base_url: str, clob_base_url: str):
        self.gamma_base_url = gamma_base_url.rstrip("/")
        self.clob_base_url = clob_base_url.rstrip("/")

        self.gamma_client = httpx.AsyncClient(
            base_url=self.gamma_base_url,
            timeout=httpx.Timeout(30.0, connect=10.0),
        )
        self.clob_client = httpx.AsyncClient(
            base_url=self.clob_base_url,
            timeout=httpx.Timeout(30.0, connect=10.0),
        )

        # In-memory cache for active markets (avoids re-fetching on every search)
        self._markets_cache: list[GammaMarket] | None = None
        self._markets_cache_time: float = 0
        self._markets_cache_ttl: float = 300  # 5 minutes

    async def aclose(self) -> None:
        await self.gamma_client.aclose()
        await self.clob_client.aclose()

    async def __aenter__(self) -> "PolymarketClient":
        return self

    async def __aexit__(self, *exc_info) -> None:
        await self.aclose()

    async def _fetch_all_active_markets(self) -> list[GammaMarket]:
        """Fetch ALL active markets from Gamma API with pagination. Results are cached."""
        now = time.monotonic()
        if self._markets_cache is not None and now - self._markets_cache_time < self._markets_cache_ttl:
            logger.debug("Returning cached active markets (%d items)", len(self._markets_cache))
            return list(self._markets_cache)

        all_markets: list[GammaMarket] = []
        limit = 100
        offset = 0
        while True:
            raw = await self._get(
                self.gamma_client, "/markets",
                params={"active": "true", "limit": str(limit), "offset": str(offset)},
            )
            markets = self._parse_markets(raw)
            if not markets:
                break
            all_markets.extend(markets)
            if len(markets) < limit:
                break
            offset += limit

        self._markets_cache = all_markets
        self._markets_cache_time = time.monotonic()
        logger.info("Fetched and cached %d active markets", len(all_markets))
        return all_markets

    async def fetch_active_markets(self) -> list[GammaMarket]:
        """Fetch ALL active markets from Gamma API with pagination. Public alias for cached fetch."""
        return await self._fetch_all_active_markets()

    async def clear_markets_cache(self) -> None:
        """Force cache invalidation."""
        self._markets_cache = None
        self._markets_cache_time = 0

    async def fetch_market(self, market_id: str) -> GammaMarket | None:
        """Fetch a single market by ID from Gamma API."""
        raw = await self._get(self.gamma_client, "/markets", params={"id": market_id})
        data = raw if isinstance(raw, list) else [raw]
        if not data:
            return None
        try:
            return GammaMarket.model_validate(data[0])
        except Exception as e:
            logger.warning("Failed to parse market %s: %s", market_id, e)
            return None

    async def search_markets(
        self,
        q: str,
        limit: int = 20,
        offset: int = 0,
        sort: str = "none",
        deadline_filter: str = "all",
    ) -> tuple[list[GammaMarket], int]:
        """Search active markets by question text with pagination.

        Uses cached market list when available. Filters client-side on the cached
        dataset to avoid fetching all 5000+ markets from Gamma API on every request.
        """
        all_markets = await self._fetch_all_active_markets()

        # Filter by query
        if q:
            q_lower = q.lower()
            all_markets = [
                m for m in all_markets
                if q_lower in m.question.lower() or q_lower in (m.description or "").lower()
            ]

        if deadline_filter == "with_deadline":
            all_markets = [m for m in all_markets if m.end_date]
        elif deadline_filter == "without_deadline":
            all_markets = [m for m in all_markets if not m.end_date]

        if sort == "soonest":
            all_markets.sort(
                key=lambda m: (m.end_date is None, m.end_date or "9999-12-31T23:59:59Z")
            )
        elif sort == "latest":
            all_markets.sort(
                key=lambda m: (m.end_date is None, m.end_date or ""),
                reverse=True,
            )

        total = len(all_markets)
        # Slice for pagination after filtering and sorting across the full result set
        page = all_markets[offset:offset + limit]
        return page, total

    async def fetch_resolved_markets(self) -> list[GammaMarket]:
        """Fetch ALL resolved markets from Gamma API with pagination."""
        all_markets: list[GammaMarket] = []
        limit = 100
        offset = 0
        while True:
            raw = await self._get(
                self.gamma_client, "/markets",
                params={"resolved": "true", "limit": str(limit), "offset": str(offset)},
            )
            markets = self._parse_markets(raw)
            if not markets:
                break
            all_markets.extend(markets)
            if len(markets) < limit:
                break
            offset += limit
        return all_markets

    async def fetch_market_prices(self, market_id: str) -> list[ClobPrice]:
        """Fetch current prices for a market from CLOB API."""
        raw = await self._get(self.clob_client, "/prices", params={"market": market_id})
        data = raw if isinstance(raw, list) else [raw]
        return [ClobPrice.model_validate(item) for item in data]

    def _parse_markets(self, raw: list[dict]) -> list[GammaMarket]:
        """Parse raw JSON into validated GammaMarket models, logging failures."""
        markets: list[GammaMarket] = []
        for item in raw:
            try:
                markets.append(GammaMarket.model_validate(item))
            except Exception as e:
                market_id = item.get("id", "unknown")
                logger.warning("Failed to parse market %s: %s", market_id, e)
        return markets

    async def _get(
        self,
        client: httpx.AsyncClient,
        path: str,
        params: dict | None = None,
        retries: int = 3,
    ) -> list[dict] | dict:
        """GET with exponential backoff. Returns parsed JSON."""
        last_error: Exception | None = None
        for attempt in range(retries):
            try:
                response = await client.get(path, params=params)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                last_error = e
                if e.response.status_code == 429 and attempt < retries - 1:
                    wait = 2**attempt
                    logger.warning("Rate limited, retrying in %ds: %s", wait, path)
                    await asyncio.sleep(wait)
                    continue
                if e.response.status_code >= 500 and attempt < retries - 1:
                    wait = 2**attempt
                    status = e.response.status_code
                    logger.warning(
                        "Server error %d, retrying in %ds: %s",
                        status, wait, path,
                    )
                    await asyncio.sleep(wait)
                    continue
                raise
            except (httpx.RequestError, ValueError) as e:
                last_error = e
                if attempt < retries - 1:
                    wait = 2**attempt
                    logger.warning("Request error, retrying in %ds: %s", wait, path)
                    await asyncio.sleep(wait)
                    continue
                raise
        msg = f"Max retries ({retries}) exceeded for {path}"
        raise RuntimeError(msg) from last_error
