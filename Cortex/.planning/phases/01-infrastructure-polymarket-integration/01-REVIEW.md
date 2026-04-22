---
phase: 01-infrastructure-polymarket-integration
reviewed: 2026-04-11T21:44:46Z
depth: standard
files_reviewed: 21
files_reviewed_list:
  - backend/app/config.py
  - backend/app/database.py
  - backend/app/main.py
  - backend/app/scheduler.py
  - backend/app/models/event.py
  - backend/app/models/prediction.py
  - backend/app/models/model_stat.py
  - backend/app/models/__init__.py
  - backend/app/schemas/event.py
  - backend/app/schemas/pagination.py
  - backend/app/schemas/polymarket.py
  - backend/app/schemas/__init__.py
  - backend/app/routers/events.py
  - backend/app/routers/__init__.py
  - backend/app/services/polymarket.py
  - backend/app/services/sync.py
  - backend/app/services/__init__.py
  - backend/tests/conftest.py
  - backend/tests/test_services/test_polymarket.py
  - backend/tests/test_services/test_sync.py
  - backend/tests/test_routers/test_events.py
findings:
  critical: 2
  warning: 4
  info: 5
  total: 11
status: issues_found
---

# Phase 01: Code Review Report

**Reviewed:** 2026-04-11T21:44:46Z
**Depth:** standard
**Files Reviewed:** 21
**Status:** issues_found

## Summary

The Phase 1 codebase establishes a solid foundation with FastAPI, SQLAlchemy async, APScheduler, and a well-structured Polymarket integration client. The retry/backoff logic, pagination, and test coverage are commendable. However, there are two critical issues with the test infrastructure that will cause intermittent failures or crashes, several warnings around async correctness and SQLAlchemy patterns, and a handful of minor quality improvements.

## Critical Issues

### CR-01: Test database engine shares event loop across fixtures

**File:** `backend/tests/conftest.py:34` and `backend/tests/conftest.py:39`

**Issue:** The `setup_test_db` fixture is `scope="session"`, but uses `asyncio.run(_setup())` to create tables. `asyncio.run()` always creates a **new** event loop. The `AsyncEngine` created at module level (`engine = create_async_engine(...)` at line 22) binds to this new loop during `create_all`. After `asyncio.run()` returns, that loop is closed. Subsequent test fixtures (`db_session`) run in pytest-asyncio's event loop, which is a **different** loop. When the engine tries to use the closed loop, it will raise `RuntimeError: Event loop is closed`.

The same problem applies to teardown at line 39.

**Fix:**
```python
@pytest.fixture(scope="session")
def setup_test_db():
    """Create test tables before tests, drop after."""
    async def _setup():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def _teardown():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)

    # Use a single event loop for both setup and teardown
    import asyncio
    loop = asyncio.new_event_loop()
    loop.run_until_complete(_setup())
    yield
    loop.run_until_complete(_teardown())
    loop.run_until_complete(engine.dispose())
    loop.close()
```

### CR-02: Test client overrides shared app state, causing cross-test pollution

**File:** `backend/tests/conftest.py:64`

**Issue:** The `client` fixture does `app.router.lifespan_context = test_lifespan`. This mutates the **shared** `app` object imported from `app.main`. Once one test overrides it, all subsequent tests importing `app.main` get the overridden version. This is not a functional bug today because the override is idempotent, but it silently masks the original lifespan and means any test that inspects `app.state` (e.g., checking `app.state.poly_client` or `app.state.scheduler`) will fail after another test has run.

**Fix:** Create a fresh app instance per test instead of mutating the global:
```python
@pytest.fixture
async def client():
    from app.main import lifespan as original_lifespan
    from app.main import app

    @asynccontextmanager
    async def test_lifespan(app):
        yield

    # Create a copy or restructure so each test gets its own app
    # Best approach: use a factory function in main.py
    # def create_app() -> FastAPI: ...
    # Then here: test_app = create_app()
    app.router.lifespan_context = test_lifespan
    app.dependency_overrides[get_db] = _get_test_db
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac
    app.dependency_overrides.clear()
    app.router.lifespan_context = original_lifespan  # Restore
```

## Warnings

### WR-01: Unnecessary exception re-raise in scheduler job causes APScheduler error logging

**File:** `backend/app/scheduler.py:25`

**Issue:** The `sync_job` function catches the exception, logs it, then re-raises it. APScheduler already logs exceptions from scheduled jobs. The re-raise causes APScheduler to log the same error a second time with its own traceback formatting. More importantly, if APScheduler is configured with an error handler that counts failures for alerting, this artificially inflates the error count.

**Fix:**
```python
async def sync_job(poly_client: PolymarketClient) -> None:
    logger.info("Running scheduled market sync...")
    async with async_session() as session:
        await sync_markets(poly_client, session)
```
Let APScheduler handle exception logging naturally, or keep the try/except but do not re-raise unless you have a specific error handler that needs the exception.

### WR-02: N+1 query pattern in market sync — individual upsert per market

**File:** `backend/app/services/sync.py:53-70`

**Issue:** The sync loop executes one `INSERT ... ON CONFLICT DO UPDATE` per market (line 53-70). For 100+ markets this means 100+ individual `session.execute()` calls. While functionally correct, this is a reliability issue because if the loop fails partway through, only the markets processed before the failure are committed (partial sync). A batch approach or transaction-per-market would be more robust.

**Fix:** Execute all inserts in a single `session.execute()` with a bulk insert:
```python
events_data = [gamma_market_to_event(m) for m in markets]
stmt = insert(Event).values(events_data)
stmt = stmt.on_conflict_do_update(
    index_elements=["polymarket_market_id"],
    set_={
        "title": stmt.excluded.title,
        # ... other fields
        "updated_at": func.now(),
    },
)
await session.execute(stmt)
await session.commit()
```

### WR-03: `db_session` test fixture rollback may not cover sessions created by `_get_test_db`

**File:** `backend/tests/conftest.py:47-52` and `backend/tests/conftest.py:74-77`

**Issue:** The `db_session` fixture creates a session bound to a connection with a pending transaction, then rolls it back at the end. But `_get_test_db` (the dependency override used by the API client) creates its **own** session from `test_session`. Because `test_session` is a sessionmaker bound to the engine (not the specific connection from the `db_session` fixture's `conn.begin()`), API requests during tests may write to a different connection that is **not** rolled back by the test fixture's `tx.rollback()`.

**Fix:** Make `_get_test_db` return the same session instance from the `db_session` fixture:
```python
@pytest.fixture
async def db_session():
    async with engine.connect() as conn:
        tx = await conn.begin()
        session = test_session(bind=conn)

        # Override get_db for this fixture scope
        async def _get_test_db_override():
            yield session

        app.dependency_overrides[get_db] = _get_test_db_override
        try:
            yield session
        finally:
            await session.close()
            await tx.rollback()
            app.dependency_overrides.pop(get_db, None)
```

### WR-04: Module-level environment mutation in test files

**File:** `backend/tests/test_services/test_polymarket.py:7-14` (and same in `conftest.py:11-18`)

**Issue:** Both test files mutate `os.environ` at module import time to remove proxy variables. This runs when the module is imported, not when tests execute. If another test file needs those proxy variables set, they will be silently removed. This also means the cleanup never happens -- the variables are never restored.

**Fix:** Move the env cleanup into a module-scoped fixture:
```python
@pytest.fixture(scope="module", autouse=True)
def clear_proxy_vars():
    proxy_vars = ("ALL_PROXY", "HTTP_PROXY", "HTTPS_PROXY", ...)
    saved = {v: os.environ.pop(v, None) for v in proxy_vars}
    yield
    for k, v in saved.items():
        if v is not None:
            os.environ[k] = v
```

## Info

### IN-01: Import inside function scope

**File:** `backend/app/routers/events.py:59`

**Issue:** `from uuid import UUID` is imported inside the `get_event` function body. This is unconventional and slightly inefficient (import is evaluated on every call).

**Fix:** Move to module-level imports at the top of the file.

### IN-02: Redundant index declarations on Event model

**File:** `backend/app/models/event.py:18` and `backend/app/models/event.py:27-29`

**Issue:** `category` column has `index=True` (line 18) and there is also an explicit `Index("ix_events_category", "category")` in `__table_args__` (line 28). This creates two separate indexes on the same column.

**Fix:** Remove the explicit `Index("ix_events_category", "category")` from `__table_args__` (keep `index=True` on the column) OR remove `index=True` and keep only the `__table_args__` version for naming control.

### IN-03: Untyped `JSONB` columns

**File:** `backend/app/models/event.py:19-20`, `backend/app/models/prediction.py:19`

**Issue:** `outcomes: Mapped[list]` and `outcome_prices: Mapped[dict]` have bare `list` and `dict` type annotations without generic parameters. Pydantic schemas also use bare `list` and `dict` in `EventResponse` (lines 15-16).

**Fix:** Use typed generics for better static analysis:
```python
outcomes: Mapped[list[str]] = mapped_column(JSONB, ...)
outcome_prices: Mapped[dict[str, float]] = mapped_column(JSONB, ...)
```

### IN-04: `from_attributes` on PaginatedResponse is unnecessary

**File:** `backend/app/schemas/pagination.py:9`

**Issue:** `PaginatedResponse` has `ConfigDict(from_attributes=True)` but the class is never populated from ORM objects -- it is always constructed from already-validated Pydantic `EventResponse` items. The setting has no effect and may confuse future maintainers about the intended usage.

**Fix:** Remove `model_config = ConfigDict(from_attributes=True)` from `PaginatedResponse`.

### IN-05: Default database URL uses Docker hostname

**File:** `backend/app/config.py:7`

**Issue:** The default `database_url` is `postgresql+asyncpg://postgres:postgres@db:5432/cortex`. The hostname `db` is a Docker Compose convention. If a developer runs the backend outside Docker (e.g., locally with `uvicorn`), the default will fail to connect. This is an info-level concern only because the fix is trivial.

**Fix:** Consider `localhost` as the default, or document that Docker Compose is required for local development.

---

_Reviewed: 2026-04-11T21:44:46Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
