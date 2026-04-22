# Phase 1: Infrastructure + Polymarket Integration - Research

**Researched:** 2026-04-12
**Domain:** FastAPI backend infrastructure, Polymarket API integration, Docker Compose, APScheduler
**Confidence:** HIGH

## Summary

This phase establishes the foundational infrastructure for Cortex: a FastAPI backend with PostgreSQL, Docker Compose for local development, Polymarket market sync via APScheduler, and a paginated REST event feed API. The phase delivers a running backend that automatically syncs Polymarket markets hourly and exposes them via a filterable API.

**Primary recommendation:** Use SQLAlchemy 2.0 with async engine + separate Pydantic schemas (not SQLModel, per user decision D-02), APScheduler 3.11.2 embedded in FastAPI lifespan, and Gamma API (`https://gamma-api.polymarket.com`) for market/event data with CLOB API (`https://clob.polymarket.com`) for pricing data.

## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Monorepo layout — `backend/` + `frontend/` directories in root. Frontend scaffolded empty on Phase 1. Single GitHub repo, auto-deploy on Railway, Dockerfile platform-agnostic (no Railway-specific hooks).
- **D-02:** SQLAlchemy + Pydantic as separate layers (not SQLModel). SQLAlchemy models for ORM, separate Pydantic schemas for API request/response validation.
- **D-03:** Alembic for database migrations — standard SQLAlchemy companion.
- **D-04:** REST API — `GET /events` (paginated, category filter), `GET /events/{id}` (detail). No GraphQL.
- **D-05:** Polymarket CLOB API for active markets + Gamma API for resolved outcomes. Wrap all responses in Pydantic models. Exponential backoff on httpx client.
- **D-06:** APScheduler with `AsyncIOScheduler`, single worker (`uvicorn --workers 1`). Idempotent upserts for market sync.
- **D-07:** All 3 tables created from Phase 1: `events`, `predictions`, `model_stats`. Foreign keys work from the start.
- **D-08:** APScheduler 3.11.x (NOT 4.x — pre-release). Embedded in FastAPI lifespan context. Hourly sync job.

### Claude's Discretion
- Exact connection pool sizing (within reasonable defaults)
- Polymarket CLOB API endpoint paths (verify at runtime — they change)
- Exact Pydantic model field names (follow Polymarket response schema)
- Dockerfile base image choice (python:3.12-slim or similar)

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| FastAPI | 0.135.3 | Backend API framework | [VERIFIED: pypi.org/project/fastapi/] Released April 1, 2026. Native async, Pydantic v2 integration, OpenAPI docs. |
| SQLAlchemy | 2.0.49 | ORM layer | [VERIFIED: pypi.org/project/sqlalchemy/] Released April 3, 2026. Industry standard Python ORM, async support via `asyncio` extension. |
| Pydantic | 2.12.5 | Validation/serialization | [VERIFIED: pypi.org/project/pydantic/] Released November 26, 2025. Required by FastAPI 0.100+. v2 features: `model_dump`, `TypeAdapter`. |
| asyncpg | 0.31.0 | Async PostgreSQL driver | [VERIFIED: pypi.org/project/asyncpg/] Released November 24, 2025. Fastest async PostgreSQL driver for Python. |
| Alembic | 1.18.4 | Database migrations | [VERIFIED: pypi.org/project/alembic/] Released February 10, 2026. Standard SQLAlchemy migration companion. |
| APScheduler | 3.11.2 | Scheduled background jobs | [VERIFIED: pypi.org/project/APScheduler/] Released December 22, 2025. 4.0.0a6 is pre-release — do NOT use in production. |
| httpx | 0.28.1 | Async HTTP client | [VERIFIED: pypi.org/project/httpx/] Released December 6, 2024. Fully async, same API as requests. Required for Polymarket API calls. |
| uvicorn | 0.44.0 | ASGI server | [VERIFIED: pypi.org/project/uvicorn/] Released April 6, 2026. Standard ASGI server for FastAPI. Must use `--workers 1` with APScheduler. |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pydantic-settings | 2.x (ships with Pydantic 2.x) | Environment configuration | For loading DATABASE_URL, POLYMARKET_API_BASE_URL from .env files |
| ruff | 0.15.10 | Linter + formatter | [VERIFIED: pypi.org/project/ruff/] Released April 9, 2026. Replaces flake8, black, isort. |
| pytest | 8.x | Test runner | Standard Python testing framework. |
| pytest-asyncio | 1.3.0 | Async test support | Required for testing FastAPI async endpoints. |

**Installation:**
```bash
# Backend production dependencies
pip install fastapi==0.135.3 uvicorn==0.44.0 sqlalchemy==2.0.49 asyncpg==0.31.0 alembic==1.18.4 APScheduler==3.11.2 httpx==0.28.1 pydantic==2.12.5 pydantic-settings

# Development dependencies
pip install ruff==0.15.10 pytest pytest-asyncio==1.3.0
```

## Architecture Patterns

### Recommended Project Structure
```
backend/
├── Dockerfile                          # Platform-agnostic Python 3.12-slim
├── pyproject.toml                      # Dependencies, ruff config, pytest config
├── alembic/
│   ├── env.py                          # Async Alembic configuration
│   ├── script.py.mako                  # Migration template
│   └── versions/                       # Migration files
│       └── 001_initial_schema.py       # Initial migration: events, predictions, model_stats
├── app/
│   ├── __init__.py
│   ├── main.py                         # FastAPI app factory, lifespan events
│   ├── config.py                       # pydantic-settings BaseSettings
│   ├── database.py                     # Async engine, session factory, get_db dependency
│   ├── scheduler.py                    # APScheduler setup, sync_events job
│   ├── models/
│   │   ├── __init__.py
│   │   ├── event.py                    # SQLAlchemy Event model
│   │   ├── prediction.py               # SQLAlchemy Prediction model
│   │   └── model_stat.py               # SQLAlchemy ModelStat model
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── event.py                    # Pydantic schemas (EventCreate, EventResponse, EventList)
│   │   └── pagination.py               # PaginatedResponse wrapper
│   ├── routers/
│   │   ├── __init__.py
│   │   └── events.py                   # GET /events, GET /events/{id}
│   └── services/
│       ├── __init__.py
│       ├── polymarket.py               # PolymarketClient class (httpx wrapper)
│       └── sync.py                     # Market sync logic (upsert patterns)
├── tests/
│   ├── __init__.py
│   ├── conftest.py                     # Test fixtures, async DB session
│   ├── test_routers/
│   │   └── test_events.py              # Event feed API tests
│   └── test_services/
│       └── test_polymarket.py          # Polymarket client tests
└── .env.example                        # Template (not committed)
```

### Pattern 1: FastAPI Lifespan with APScheduler
**What:** Embed APScheduler in FastAPI's lifespan context for proper startup/shutdown
**When to use:** Always — this is the only supported way to run APScheduler with FastAPI
**Example:**
```python
from contextlib import asynccontextmanager
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI

scheduler = AsyncIOScheduler()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: start scheduler
    scheduler.add_job(sync_events, "interval", hours=1, id="sync_events", replace_existing=True)
    scheduler.start()
    yield
    # Shutdown: stop scheduler
    scheduler.shutdown()

app = FastAPI(lifespan=lifespan)
```

### Pattern 2: Async SQLAlchemy with Dependency Injection
**What:** Async engine with `async_sessionmaker`, injected into route handlers
**When to use:** All database operations in FastAPI
**Example:**
```python
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

engine = create_async_engine(
    settings.DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,  # Detect stale connections
)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
        yield session
```

### Pattern 3: Idempotent Upsert for Market Sync
**What:** Insert or update market records by Polymarket market ID — prevents duplicates on repeated sync
**When to use:** APScheduler sync jobs
**Example:**
```python
from sqlalchemy.dialects.postgresql import insert

async def upsert_event(session: AsyncSession, event_data: dict):
    stmt = insert(Event).values(**event_data)
    stmt = stmt.on_conflict_do_update(
        index_elements=["polymarket_market_id"],
        set_={
            "title": stmt.excluded.title,
            "updated_at": func.now(),
        }
    )
    await session.execute(stmt)
```

### Anti-Patterns to Avoid
- **APScheduler 4.x:** Pre-release version with no migration guarantee. Use 3.11.2 only.
- **`@app.on_event("startup")`:** Deprecated in FastAPI. Use lifespan context manager instead.
- **`BackgroundTasks` for scheduling:** In-memory, loses state on restart. Use APScheduler for persistent scheduling.
- **`requests` for HTTP:** Blocking — blocks the event loop. Use `httpx` exclusively.
- **`insert()` instead of upsert:** Will create duplicate records on every sync. Always use `on_conflict_do_update`.
- **SQLModel:** Per decision D-02, do NOT use SQLModel. Use separate SQLAlchemy models and Pydantic schemas.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Database migrations | Custom schema versioning | Alembic | Handles dependency graph, rollback, alembic upgrade/downgrade. Edge cases with column renames are complex. |
| Environment config | `os.environ.get()` with manual defaults | pydantic-settings | Type validation, `.env` file loading, clear config classes with defaults. |
| Polymarket API client | `httpx.get(url)` inline | Dedicated `PolymarketClient` class | Centralized error handling, exponential backoff, typed responses, retry logic, rate limit awareness. |
| Pagination | Manual OFFSET/LIMIT in each route | Reusable pagination schema + query helpers | Consistent API, total count, next/prev cursors, avoids off-by-one errors. |

**Key insight:** The infrastructure layer is thin — don't overengineer. The custom orchestration value is in the forecast agent (Phase 2), not in reinventing database patterns.

## Polymarket API Integration

### Available APIs (verified from docs.polymarket.com)

| API | Base URL | Auth | Purpose |
|-----|----------|------|---------|
| **Gamma API** | `https://gamma-api.polymarket.com` | None (public) | Events, markets, tags, series, search, resolved outcomes |
| **CLOB API** | `https://clob.polymarket.com` | None for public endpoints | Orderbook data, pricing, midpoints, spreads, price history |
| **Data API** | `https://data-api.polymarket.com` | None (public) | User positions, trades, open interest, leaderboards |

### Strategy for Phase 1

**Gamma API is the primary source** for Phase 1 because:
- It provides **events** and **markets** with full metadata (title, description, category, outcomes, resolution)
- Public endpoints require no authentication
- Supports filtering by status (active, resolved, closed)

**CLOB API is secondary** for:
- Real-time pricing data (midpoint, spread, volume)
- Orderbook depth (useful for Phase 2+ when analyzing market sentiment)

### Endpoint Verification Required

**[ASSUMED]** The following endpoint patterns are based on common Polymarket client implementations and may have changed. The planner must verify these at implementation time:

- Gamma API: `/markets`, `/events`, `/markets?active=true`, `/markets?resolved=true` (parameter-based filtering)
- CLOB API: `/markets`, `/prices`, `/midpoint` (pricing endpoints)

The project's own STATE.md flagged: "Polymarket CLOB API endpoints may have changed - verify at implementation time." **This is a known risk.**

### Pydantic Response Models

All Polymarket API responses must be wrapped in Pydantic models to:
1. Fail loudly on schema changes (early detection of API updates)
2. Normalize field names to our internal schema
3. Strip unnecessary fields before database insertion

```python
from pydantic import BaseModel, Field

class PolymarketMarket(BaseModel):
    condition_id: str
    question: str
    description: str
    outcomes: list[str]
    outcome_prices: dict[str, float]  # outcome -> price mapping
    active: bool
    closed: bool
    category: str
    end_date_iso: str | None = None
```

## Common Pitfalls

### Pitfall 1: APScheduler Duplicate Jobs (Multi-Worker Trap)
**What goes wrong:** Running uvicorn with `--workers > 1` spawns multiple processes, each starting its own scheduler. Market sync fires N times per hour, creating duplicate events.
**Why it happens:** APScheduler is in-process — it doesn't know about other workers.
**How to avoid:** Always run `uvicorn --workers 1` in production. Log scheduler startup with PID to detect if multiple schedulers start.
**Warning signs:** Same market sync fires multiple times in logs; duplicate events with same Polymarket ID.

### Pitfall 2: Database Connection Pool Exhaustion
**What goes wrong:** APScheduler jobs and HTTP requests share the same engine. If pool is too small, requests hang waiting for connections.
**Why it happens:** APScheduler job runs on the event loop, consuming pool connections. If all connections are busy, new requests block.
**How to avoid:** Set `pool_size=10`, `max_overflow=20`, `pool_pre_ping=True`. APScheduler job should create its own session context. Monitor `pg_stat_activity` in dev.
**Warning signs:** `Too many connections` errors; requests hanging on DB operations.

### Pitfall 3: Polymarket API Schema Changes
**What goes wrong:** Polymarket changes response fields without notice. Sync job starts failing silently or importing bad data.
**Why it happens:** External API — no version guarantee, no deprecation notices.
**How to avoid:** Wrap ALL responses in Pydantic models (fail loudly). Log raw responses on parse failure. Cache last successful sync result.
**Warning signs:** Sudden Pydantic ValidationError in sync logs; missing fields in API responses.

### Pitfall 4: CORS Misconfiguration
**What goes wrong:** Frontend can't reach backend in production. CORS errors in browser console.
**Why it happens:** CORS origins not configured for frontend URL, or `*` used in production.
**How to avoid:** Use environment variable for frontend URL. Configure CORS with explicit origins. Test with frontend deployment, not just localhost.
**Warning signs:** API works in curl but not from browser; `Access-Control-Allow-Origin` errors.

### Pitfall 5: Environment Variable Leaks
**What goes wrong:** API keys exposed in Docker image or committed .env files.
**Why it happens:** `.env` files not in `.gitignore`, or secrets baked into Dockerfile.
**How to avoid:** `.env` and `.env.local` in `.gitignore`. Use `.env.example` as template. Railway injects env vars at runtime — no .env files deployed.
**Warning signs:** `.env` file appears in git history; Docker image contains secrets.

### Pitfall 6: Alembic Async Configuration
**What goes wrong:** Alembic migrations fail because they use sync SQLAlchemy engine instead of async.
**Why it happens:** Default Alembic template uses sync engine. Must be configured for `postgresql+asyncpg://`.
**How to avoid:** Configure `alembic/env.py` to use `create_async_engine` with `run_async_migrations()`. Use `asyncio.run()` wrapper in env.py.
**Warning signs:** `AsyncEngine` errors when running `alembic upgrade head`; sync connection errors.

## Code Examples

### Alembic Async Configuration (env.py)
```python
# Source: https://alembic.sqlalchemy.org/en/latest/asyncio.html
from sqlalchemy.ext.asyncio import async_engine_from_config
from alembic import context
import asyncio

def run_migrations_offline():
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()

def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()

async def run_async_migrations():
    """Run migrations in 'online' mode with async engine."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()

def run_migrations_online():
    asyncio.run(run_async_migrations())
```

### Polymarket Client with Exponential Backoff
```python
import httpx
from typing import Any

class PolymarketClient:
    def __init__(self, base_url: str = "https://gamma-api.polymarket.com"):
        self.base_url = base_url.rstrip("/")
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(30.0, connect=10.0),
        )

    async def fetch_active_markets(self) -> list[dict[str, Any]]:
        """Fetch all active markets from Gamma API."""
        response = await self._get("/markets", params={"active": "true"})
        return response.json()

    async def fetch_resolved_markets(self) -> list[dict[str, Any]]:
        """Fetch resolved markets from Gamma API."""
        response = await self._get("/markets", params={"resolved": "true"})
        return response.json()

    async def _get(self, path: str, params: dict | None = None, retries: int = 3) -> httpx.Response:
        """GET with exponential backoff."""
        for attempt in range(retries):
            try:
                response = await self.client.get(path, params=params)
                response.raise_for_status()
                return response
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429 and attempt < retries - 1:
                    wait = 2 ** attempt  # 1s, 2s, 4s
                    await asyncio.sleep(wait)
                    continue
                raise
        raise RuntimeError(f"Max retries ({retries}) exceeded for {path}")
```

### FastAPI Lifespan with APScheduler
```python
from contextlib import asynccontextmanager
from apscheduler.schedulers.asyncio import AsyncIOScheduler

scheduler = AsyncIOScheduler()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Configure DB engine
    engine = create_async_engine(settings.database_url, pool_size=10, max_overflow=20)

    # Create Polymarket client
    poly_client = PolymarketClient(base_url=settings.polymarket_gamma_api_url)

    # Store in app state for router access
    app.state.engine = engine
    app.state.poly_client = poly_client

    # Add scheduler jobs
    scheduler.add_job(
        sync_markets,
        "interval",
        hours=1,
        id="sync_markets",
        replace_existing=True,
        args=[app],
    )
    scheduler.start()

    yield

    # Shutdown
    scheduler.shutdown()
    await engine.dispose()

app = FastAPI(lifespan=lifespan)
```

### Pagination Schema
```python
from pydantic import BaseModel

class PaginatedResponse[T](BaseModel):
    items: list[T]
    total: int
    page: int
    page_size: int
    has_next: bool
    has_prev: bool
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `@app.on_event("startup")` | `@asynccontextmanager` lifespan | FastAPI 0.100+ | Graceful shutdown, proper context |
| `requests` | `httpx` async | Ongoing | Non-blocking, same API |
| APScheduler sync `BlockingScheduler` | `AsyncIOScheduler` | APScheduler 3.6+ | Runs in same event loop as FastAPI |
| Manual `.env` parsing | `pydantic-settings` BaseSettings | Pydantic v2 | Type validation, IDE autocomplete |
| `SQLAlchemy 1.x` core | `SQLAlchemy 2.0` asyncio | SQLAlchemy 2.0 (2023) | Native async, `select()` syntax |
| `alembic --autogenerate` sync only | Async-compatible Alembic env.py | Ongoing | Works with asyncpg |

**Deprecated/outdated:**
- **APScheduler 4.x:** Explicitly pre-release. README warns against production use. Use 3.11.2.
- **SQLModel for this project:** Per decision D-02, using separate SQLAlchemy + Pydantic layers.
- **`python-jose`:** Unmaintained since 2021. Use PyJWT (though not needed in Phase 1).

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Gamma API `/markets` endpoint supports `?active=true` and `?resolved=true` query parameters | Polymarket API Integration | Sync job may need different filtering approach — endpoint paths need runtime verification |
| A2 | `pool_size=10, max_overflow=20` is appropriate for Railway's free/low-tier PostgreSQL | Architecture Patterns | Railway may have lower connection limits — may need to reduce pool size |
| A3 | PostgreSQL supports `INSERT ... ON CONFLICT DO UPDATE` (upsert) via SQLAlchemy | Architecture Patterns | This is standard PostgreSQL since 9.5 — very low risk |
| A4 | Polymarket Gamma API does not require API key for read operations | Polymarket API Integration | If auth becomes required, sync jobs will fail until key is obtained |
| A5 | `pydantic-settings` version aligns with Pydantic 2.12.5 | Standard Stack | Minor API differences possible — verify import path |

## Open Questions

1. **Polymarket Gamma API exact endpoint paths**
   - What we know: Gamma API base URL is `https://gamma-api.polymarket.com`. Public endpoints exist for markets and events.
   - What's unclear: Exact query parameter names for filtering (is it `?active=true` or `?status=active`? Is there a pagination parameter?)
   - Recommendation: Implement the PolymarketClient with configurable base URL and endpoint paths. Test with a quick curl at implementation time.

2. **Railway PostgreSQL connection limits**
   - What we know: Railway provides managed PostgreSQL. Default pool size recommendations are 10/20.
   - What's unclear: Exact connection limit on Railway's free tier (may be as low as 20-50 connections)
   - Recommendation: Start with conservative pool_size=5, max_overflow=10. Monitor and adjust.

3. **Event categorization strategy**
   - What we know: Polymarket markets have categories/tags. We need category filtering in the API.
   - What's unclear: How Polymarket structures categories — flat tags, hierarchical, or free-text
   - Recommendation: Store categories as-is from Polymarket response. API filtering can be `?category=` (single) or `?categories=a,b` (multiple).

4. **Market vs Event granularity**
   - What we know: Polymarket has both "events" (higher-level) and "markets" (individual outcome questions).
   - What's unclear: Should our `events` table map to Polymarket events or markets? One Polymarket event can contain multiple markets.
   - Recommendation: Map our `events` table to Polymarket **events** (higher level), and have a `markets` table for individual markets. This supports the "prediction journal per event" requirement. However, for Phase 1 simplicity, consider starting with a single `events` table that maps to Polymarket **markets** (since that's what users actually predict on). The schema can be normalized later.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | Backend runtime | ✓ | 3.12.3 | — |
| pip | Package management | ✓ | 24.0 | — |
| Docker | Docker Compose local dev | ✗ | — | Manual setup: install PostgreSQL locally, run backend with `uvicorn` |
| Docker Compose | Local dev orchestration | ✗ | — | Manual setup: `docker-compose.yml` requires Docker |
| PostgreSQL | Database | ✗ | — | Use Docker Compose to spin up locally, or Railway managed DB |
| Node.js | Frontend (scaffold only) | ✓ | v18.19.1 | — |

**Missing dependencies with no fallback:**
- Docker/Docker Compose — required by INF-01. Must be installed for local development. The plan should include installation instructions or flag this as a prerequisite.

**Missing dependencies with fallback:**
- PostgreSQL can be substituted with a Railway-managed instance for testing, but local dev requires Docker Compose or a local PostgreSQL install.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.x + pytest-asyncio 1.3.0 |
| Config file | `backend/pyproject.toml` (pytest section) |
| Quick run command | `cd backend && pytest tests/ -x -q` |
| Full suite command | `cd backend && pytest tests/ -v --tb=short` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| INF-01 | Docker Compose starts backend + PostgreSQL | integration | `docker compose up -d && docker compose ps` | ❌ |
| INF-02 | APScheduler sync job runs hourly, upserts markets | unit + integration | `pytest tests/test_services/test_sync.py -x` | ❌ |
| INF-03 | GET /events returns paginated results with category filter | unit | `pytest tests/test_routers/test_events.py -x` | ❌ |

### Sampling Rate
- **Per task commit:** `cd backend && pytest tests/ -x -q`
- **Per wave merge:** `cd backend && pytest tests/ -v --tb=short`
- **Phase gate:** All 3 test files created and passing before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `backend/tests/conftest.py` — shared fixtures (async DB session, test client, Polymarket mock client)
- [ ] `backend/tests/test_routers/test_events.py` — covers INF-03
- [ ] `backend/tests/test_services/test_sync.py` — covers INF-02
- [ ] `backend/tests/test_services/test_polymarket.py` — Polymarket client unit tests
- [ ] Framework install: `pip install pytest pytest-asyncio` — add to dev dependencies
- [ ] `backend/pyproject.toml` — pytest config section (`asyncio_mode = "auto"`)

## Security Domain

> Phase 1 has no authentication, no user input beyond query parameters, and no secrets beyond API keys (handled by environment variables). Security domain is minimal.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V5 Input Validation | yes | Pydantic models for query parameter validation (page, page_size, category) |
| V6 Cryptography | no | No encryption needed in Phase 1 |
| V10 Malicious Code Prevention | yes | Pydantic validation on all external API responses |
| V11 API Security | yes | CORS configuration, rate limiting (future) |

### Known Threat Patterns for Phase 1

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Query parameter injection | Tampering | Pydantic validation on pagination params (page >= 1, page_size <= 100) |
| CORS misconfiguration | Information Disclosure | Explicit origin list, not `*` |
| Environment variable leaks | Information Disclosure | `.env` in `.gitignore`, `.env.example` committed |
| Polymarket API data poisoning | Tampering | Pydantic models fail on unexpected schema changes |

## Sources

### Primary (HIGH confidence)
- **PyPI: FastAPI 0.135.3** — [pypi.org/project/fastapi/] (verified April 1, 2026)
- **PyPI: SQLAlchemy 2.0.49** — [pypi.org/project/sqlalchemy/] (verified April 3, 2026)
- **PyPI: APScheduler 3.11.2** — [pypi.org/project/APScheduler/] (verified December 22, 2025)
- **PyPI: asyncpg 0.31.0** — [pypi.org/project/asyncpg/] (verified November 24, 2025)
- **PyPI: httpx 0.28.1** — [pypi.org/project/httpx/] (verified)
- **PyPI: Alembic 1.18.4** — [pypi.org/project/alembic/] (verified February 10, 2026)
- **PyPI: Pydantic 2.12.5** — [pypi.org/project/pydantic/] (verified)
- **PyPI: uvicorn 0.44.0** — [pypi.org/project/uvicorn/] (verified April 6, 2026)
- **PyPI: ruff 0.15.10** — [pypi.org/project/ruff/] (verified April 9, 2026)
- **Polymarket docs** — [docs.polymarket.com/] — API base URLs and public endpoint verification
- **Alembic asyncio docs** — [alembic.sqlalchemy.org/en/latest/asyncio.html] — async migration configuration

### Secondary (MEDIUM confidence)
- **CLAUDE.md project constraints** — verified stack choices, library recommendations
- **CONTEXT.md decisions** — D-01 through D-08 locked decisions
- **PITFALLS.md** — Pitfalls #3, #7, #9, #10 mapped to Phase 1

### Tertiary (LOW confidence)
- **Polymarket Gamma API endpoint paths** — exact query parameters (`?active=true` vs `?status=active`) need runtime verification
- **Railway PostgreSQL connection limits** — free tier limits not publicly documented

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all versions verified from PyPI within the last 24 hours
- Architecture: HIGH — patterns from official FastAPI and APScheduler documentation
- Polymarket API: MEDIUM — base URLs verified, but exact endpoint paths need runtime verification
- Pitfalls: HIGH — sourced from official docs and project PITFALLS.md

**Research date:** 2026-04-12
**Valid until:** 2026-05-12 (30 days — stable stack, but Polymarket API should be re-verified before implementation)

## RESEARCH COMPLETE
