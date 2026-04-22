---
status: verifying
trigger: "При открытии вкладки событий в админке делается запрос на выгрузку ВСЕХ событий с Polymarket (более 5000) — это превысило лимит сетевого трафика на Railway"
created: 2026-04-15T00:00:00Z
updated: 2026-04-15T00:02:00Z
---

## Current Focus
hypothesis: FIX VERIFIED — cache with TTL eliminates repeated full-market downloads
test: All cache tests pass (18/18), fix committed as da6ab25
expecting: Human verification — restart backend, open admin events tab, verify only one full download on first search, subsequent searches use cache
next_action: Request human verification

## Symptoms

expected: Админка загружает только необходимые данные о событиях, минимальный трафик
actual: При загрузке вкладки "events" в админке загружаются все 5000+ событий с Polymarket CLOB API
errors: Превышение лимита сетевого трафика на Railway
reproduction: Открыть вкладку событий в админке → идёт запрос на Polymarket API за всеми событиями
started: Обнаружено при превышении лимита Railway

## Eliminated

## Evidence

- timestamp: 2026-04-15T00:01:00Z
  checked: frontend/app/admin/page.tsx line 104-120
  found: Events tab calls searchPolymarket(debouncedSearch, EVENTS_PAGE_SIZE, searchPage * EVENTS_PAGE_SIZE) on mount and on search/page change
  implication: Frontend triggers search on every tab switch to "events"

- timestamp: 2026-04-15T00:01:00Z
  checked: frontend/lib/api.ts line 249-259
  found: searchPolymarket calls GET /api/admin/polymarket/search?q=&limit=20&offset=0
  implication: Search API receives paginated request params

- timestamp: 2026-04-15T00:01:00Z
  checked: backend/app/routers/admin.py line 171-195
  found: /api/admin/polymarket/search calls poly_client.search_markets(q=q, limit=limit, offset=offset)
  implication: Backend endpoint delegates to PolymarketClient

- timestamp: 2026-04-15T00:01:00Z
  checked: backend/app/services/polymarket.py line 68-104
  found: search_markets() iterates through ALL active markets from Gamma API (while True loop, 100 per page) before filtering client-side. Each request downloads 5000+ complete GammaMarket objects including outcomes, outcome_prices, tags, description, etc.
  implication: ROOT CAUSE — every search request (including empty query on tab open) fetches ALL markets from Polymarket API, consuming massive bandwidth

- timestamp: 2026-04-15T00:02:00Z
  checked: backend/app/services/polymarket.py after fix
  found: Added _markets_cache, _markets_cache_time, _markets_cache_ttl (300s). _fetch_all_active_markets() checks cache before hitting API. search_markets() uses cached version. clear_markets_cache() for invalidation.
  implication: First search downloads all markets once, subsequent searches within 5 min use in-memory cache

## Resolution

root_cause: "search_markets() in polymarket.py fetched ALL 5000+ active markets from Gamma API on every request (while True loop with 100/page pagination) before client-side filtering. Opening admin events tab triggered full download every time."
fix: "Added in-memory cache with 5-minute TTL to PolymarketClient. First search populates cache, subsequent searches within TTL reuse cached data without hitting Polymarket API. Added clear_markets_cache() for explicit invalidation."
verification: "All 18 tests pass (including 3 new cache tests). Committed as da6ab25."
files_changed:
  - backend/app/services/polymarket.py
  - backend/tests/test_services/test_polymarket.py
