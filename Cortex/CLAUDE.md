<!-- GSD:project-start source:PROJECT.md -->
## Project

**Cortex**

AI-платформа для прогнозирования событий на Polymarket. Подключаемые LLM-агенты исследуют интернет, анализируют новости и мнения экспертов, после чего выдают взвешенный прогноз с указанием источников. Каждый прогноз сохраняется в журнал — так можно отследить, какие модели действительно угадывают. Публичный сайт с авторизацией (вайтлист на этапе тестирования), freemium-модель: бесплатно — лимитированные прогнозы базовыми моделями, платно — безлимит + премиум модели.

**Core Value:** Наглядное сравнение точности разных AI-моделей в прогнозировании реальных событий — чтобы любой пользователь видел, какие модели действительно угадывают, а какие нет.

### Constraints

- **Tech stack:** Python/FastAPI + Next.js — уже выбраны, не менять без веской причины
- **Хостинг:** Railway — все три сервиса (backend, frontend, PostgreSQL) из одного монорепозитория
- **Модели:** v1 — только бесплатные модели через OpenRouter; платные модели подключаются в v2
- **Бюджет:** бесплатные API-ключи для старта, расходы на Railway минимальны
- **Конвенции:** conventional commits, async/await, strict TypeScript, pydantic v2
<!-- GSD:project-end -->

<!-- GSD:stack-start source:research/STACK.md -->
## Technology Stack

## Recommended Stack
### Core Technologies
| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Python | 3.12 | Backend runtime | Project constraint. Excellent async, type hints, rich ecosystem for data science (scikit-learn for Brier Score). |
| FastAPI | 0.135.x | Backend API framework | Project constraint. Best async performance in Python, native OpenAPI docs, Pydantic v2 integration, lifespan events for APScheduler. |
| Next.js | 14 (App Router) | Frontend framework | Project constraint. Server Components reduce bundle, built-in SSR for SEO, mature ecosystem. |
| TypeScript | 5.x | Frontend type safety | Project constraint (strict mode). Catches 70%+ of frontend bugs at compile time. |
| PostgreSQL | 15+ (managed on Railway) | Primary database | Project constraint. Best relational DB for structured market/prediction data. ACID compliance critical for financial prediction records. |
| OpenRouter | API | LLM model routing | Project constraint. Single API key for 300+ models, model fallbacks, `:free` tier for v1 cost control, official Python SDK. |
| Tavily | API | AI-optimized web search | Project constraint. Purpose-built for LLM agents, returns ranked content ready for context, official Python SDK with async support. |
### Backend Supporting Libraries
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **SQLModel** | 0.0.38 | ORM + Pydantic models | **Recommended for this project.** Created by FastAPI author. Single type annotation serves as SQLAlchemy model, Pydantic schema, and FastAPI request/response type. Eliminates duplicate schema definitions. |
| **SQLAlchemy** | 2.0.49 | Database engine/async | Underlying engine for SQLModel. Use `create_async_engine` with `asyncpg` driver for fully async database operations in FastAPI. |
| **asyncpg** | 0.31.0 | Async PostgreSQL driver | Fastest async PostgreSQL driver for Python. Required by SQLAlchemy 2.0 async engine. |
| **Alembic** | 1.18.4 | Database migrations | Required for schema evolution. Works with SQLModel via `sqlmodel.ModelRegistry`. Must configure for async PostgreSQL URL (`postgresql+asyncpg://`). |
| **Pydantic** | 2.12.x | Validation/serialization | Project constraint (v2). Native FastAPI integration. Use `BaseModel` for request/response schemas, `pydantic-settings` for env config. |
| **APScheduler** | 3.11.x | Scheduled background jobs | Project constraint for market sync and Brier recalculation. Use `AsyncIOScheduler` with FastAPI lifespan events. **Do NOT use APScheduler 4.x in production** — it is pre-release with no migration guarantee. |
| **openrouter** | 0.8.1 | OpenRouter API client | Official Python SDK. Type-safe access to 300+ models. Use over raw httpx for built-in model listing, provider info, and structured outputs support. |
| **tavily-python** | 0.7.23 | Tavily API client | Official SDK. Use `AsyncTavilyClient` for async web search in agents. Supports search, extract, research endpoints. |
| **httpx** | 0.28.1 | Async HTTP client | For Polymarket CLOB API calls and any other external APIs. Use over requests (requests is blocking). |
| **PyJWT** | 2.12.1 | JWT token encoding/decoding | Standard library for JWT. Use for httpOnly cookie auth tokens. Over python-jose (outdated, less maintained). |
| **passlib[bcrypt]** | 1.7.4 + bcrypt 5.0.0 | Password hashing | Project constraint. bcrypt 5.0.0 is current. passlib provides the interface, bcrypt provides the algorithm. Use bcrypt with default rounds (12+). |
| **uvicorn** | 0.44.0 | ASGI server | Project constraint. Standard ASGI server for FastAPI. Use with `--reload` in dev, `--workers 1` in prod (APScheduler is single-process; see Pitfalls). |
### Agent Orchestration (Custom, Not Framework)
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **httpx** | 0.28.1 | Agent HTTP operations | Agent uses this for Tavily search calls and Polymarket API calls. |
| **openrouter** | 0.8.1 | Agent LLM reasoning | Agent uses this for analysis and prediction generation. |
| **tavily-python** | 0.7.23 | Agent web research | Agent uses this for information gathering about prediction events. |
| **Custom agent class** | — | Research orchestration | **Do NOT use LangChain/LangGraph/CrewAI for v1.** The agent flow is simple: search -> analyze -> predict. A custom class with 3-4 methods is 10x less overhead than framework plumbing. Reconsider LangGraph in v2 if adding multi-agent collaboration. |
### Frontend Supporting Libraries
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **Tailwind CSS** | 3.4+ / 4.x | Styling | Project constraint. Utility-first, fast iteration. For v1, stick with Tailwind 3.x (stable, more tutorials). Tailwind 4.x is newer but tooling ecosystem still maturing. |
| **shadcn/ui** | Latest | Component library | Copy-paste Radix-based components. Zero dependency overhead, fully customizable. Ideal for dashboard UI (tables, cards, charts, forms). Over MUI (too heavy, opinionated styling) and Chakra (CSS-in-JS overhead with Next.js App Router). |
| **TanStack Query (React Query)** | 5.x | Server state management | For client-side data fetching from FastAPI. Handles caching, refetching, optimistic updates. Over SWR (less mature) and Redux (boilerplate-heavy, unnecessary for server state). |
| **Recharts** | 2.x | Charts | For Brier Score visualization and prediction accuracy graphs. Declarative, composable, works well with Tailwind. Over Chart.js (imperative API) and D3 (too low-level). |
| **TanStack Table** | 8.x | Data tables | For event feed with sorting, filtering, pagination. Headless (you style it). Over MUI Table (heavy) and react-table v7 (deprecated). |
### Development Tools
| Tool | Purpose | Notes |
|------|---------|-------|
| **ruff** | 0.15.x — Linter + formatter | Replaces flake8, black, isort, pyupgrade. Single tool, 100x faster. Configure `pyproject.toml` with `select = ["E", "F", "I", "N", "W", "UP", "B"]`. |
| **mypy** | 1.x — Type checker | Required for strict TypeScript-like type safety in Python. Use with `--strict`. Pydantic models are automatically typed. |
| **pytest** | 8.x — Test runner | Standard Python testing. Use with `pytest-asyncio` for async tests. |
| **pytest-asyncio** | 1.3.0 — Async test support | Required for testing FastAPI async endpoints. Configure `asyncio_mode = "auto"` in `pyproject.toml`. |
| **httpx** | 0.28.1 — Async test client | Use with `ASGITransport` for FastAPI integration tests. Pair with `asgi-lifespan` for lifespan event testing. |
| **asgi-lifespan** | 2.x — Lifespan testing | Use with httpx.AsyncClient to trigger FastAPI lifespan events in tests (scheduler startup, DB connections). |
| **Docker Compose** | 2.x — Local dev orchestration | Backend + frontend + PostgreSQL in one command. Railway uses Dockerfile for deployment. |
| **Vitest** | 2.x — Frontend tests | For Next.js component and utility tests. Faster than Jest, native ESM. |
| **Playwright** | 1.x — E2E tests | Browser automation for critical user flows (register, request prediction, view leaderboard). |
## Installation
# Backend Core
# Database
# Scheduling
# AI / LLM
# HTTP
# Auth
# Dev Tools
# Frontend
# Frontend Dev
## Alternatives Considered
| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| SQLModel | Plain SQLAlchemy 2.0 | If you need fine-grained SQLAlchemy control (complex relationships, hybrid properties) that SQLModel's simplified API can't express. For this project's relatively flat schema, SQLModel is sufficient. |
| APScheduler 3.x | Celery + Redis | If you need distributed task execution (multiple workers), retry queues, or task result tracking. For v1 single-worker Railway deployment, APScheduler is simpler (no Redis dependency). Reconsider at 10K+ users. |
| APScheduler 3.x | Arq (async Redis queue) | Same as Celery but async-native. Better for async tasks but requires Redis. Only if you add Redis anyway. |
| Custom agent class | LangGraph / CrewAI | If v2 adds multi-agent collaboration, tool-use graphs, or human-in-the-loop workflows. For v1 single-agent research -> predict flow, frameworks add 10x complexity for 1.2x benefit. |
| TanStack Query | SWR | If you prefer Vercel-maintained library with simpler API. TanStack Query has better cache management and TypeScript types. |
| Recharts | Chart.js | If you prefer imperative canvas-based rendering for performance. Recharts is SVG-based and easier to customize with React. For dashboard-scale data, performance difference is negligible. |
| openrouter SDK | Direct openai SDK with base_url override | OpenRouter is OpenAI-compatible. `openai.OpenAI(base_url="https://openrouter.ai/api/v1")` works and is well-documented. However, the official `openrouter` SDK provides model listing, provider info, and type safety specific to OpenRouter's features (`:free`, `:extended` suffixes). Use openrouter SDK for v1; fall back to openai SDK if openrouter SDK has issues. |
## What NOT to Use
| Avoid | Why | Use Instead |
|-------|-----|-------------|
| **APScheduler 4.x** | Pre-release. GitHub README explicitly warns "may change in backwards incompatible fashion without migration pathway." Breaking changes guaranteed. | APScheduler 3.11.x stable. `AsyncIOScheduler` is the class to use. |
| **APScheduler 3.x `@app.on_event("startup")`** | Deprecated in FastAPI. Will be removed. No lifespan context = no graceful shutdown. | FastAPI lifespan context manager with `@asynccontextmanager`. |
| **requests (blocking HTTP)** | Blocks the event loop in async FastAPI. Kills concurrency. | httpx (fully async, same API). |
| **python-jose** | Unmaintained since 2021. Security concerns in JWT space. | PyJWT (actively maintained, current version 2.12.1). |
| **LangChain for simple agent** | 800+ dependencies, steep learning curve, overkill for search -> analyze -> predict. Debugging is painful. | Custom Python class with httpx + Tavily + OpenRouter. 50 lines vs 500. |
| **MongoDB** | No relational integrity for prediction records. Can't enforce foreign keys between users, predictions, markets. Brier Score calculations need JOINs. | PostgreSQL (project constraint, correct choice). |
| **Redux/Zustand for server state** | Server state should be managed by TanStack Query, not global state. Client state (UI filters, modals) can use React Context. | TanStack Query for server state, React Context for simple UI state. |
| **Tailwind 4.x for v1** | New major version. Tooling ecosystem (IDE plugins, PostCSS configs) still stabilizing. Migration from 3.x may break. | Tailwind 3.x (battle-tested, abundant tutorials). Reconsider for v2. |
| **FastAPI `BackgroundTasks`** | In-memory, per-request. No persistence, no scheduling, no retries. Loses tasks on restart. | APScheduler with lifespan events for scheduled jobs. |
| **SQLAlchemy sync engine** | Blocks the event loop. Defeats the purpose of async FastAPI. Every DB call stalls all other requests. | SQLAlchemy async engine with `asyncpg` driver. |
## Stack Patterns by Variant
- Use APScheduler 3.x with `AsyncIOScheduler` embedded in FastAPI lifespan
- Run uvicorn with `--workers 1` (APScheduler is not multi-worker safe; multiple workers = duplicate scheduled jobs)
- PostgreSQL via `postgresql+asyncpg://` connection string
- This is the v1 configuration
- Replace APScheduler with Celery + Redis or Arq
- Use PostgreSQL advisory locks if keeping APScheduler (complex, not recommended)
- Revisit at >100 RPS
- Custom agent class: `class PredictionAgent` with `async def research(event_name)`, `async def analyze(findings)`, `async def predict(analysis)`
- Each step returns structured Pydantic models
- No framework overhead
- Migrate to LangGraph for multi-step reasoning with tool use
- Add Tavily search as a LangGraph tool node
- Add LLM analysis as a separate node
- This is when the framework overhead pays off
## Version Compatibility
| Package A | Compatible With | Notes |
|-----------|-----------------|-------|
| SQLModel 0.0.38 | SQLAlchemy 2.0.x, Pydantic 2.x | SQLModel is thin layer over both. Requires SQLAlchemy 2.0+ and Pydantic v2+. |
| FastAPI 0.135.x | Pydantic 2.12.x | FastAPI 0.100+ requires Pydantic v2. No backwards compatibility with Pydantic v1. |
| APScheduler 3.11.x | Any Python 3.8+ | Does NOT require async FastAPI. `AsyncIOScheduler` runs in the same event loop. |
| asyncpg 0.31.0 | PostgreSQL 12+, Python 3.8+ | Requires PostgreSQL server >= 12. Railway default is 15+. |
| openrouter 0.8.1 | Python 3.9+ | Requires Python 3.9.2+. Compatible with Python 3.12 project constraint. |
| tavily-python 0.7.23 | Python 3.8+ | Provides both sync and async clients. Use `AsyncTavilyClient` in FastAPI. |
| PyJWT 2.12.1 | Python 3.8+ | No breaking changes from 2.8+. Stable API. |
| bcrypt 5.0.0 | passlib 1.7.4 | passlib uses bcrypt as backend. bcrypt 5.0 removed deprecated APIs — passlib 1.7.4 still compatible. |
| pytest-asyncio 1.3.0 | pytest 8.x | Use `asyncio_mode = "auto"` for automatic async test detection. |
## Polymarket CLOB API Integration Notes
- Use `httpx.AsyncClient` with base URL configuration
- Wrap in a `PolymarketClient` class with typed Pydantic response models
- Cache market data to avoid rate limit issues
- Schedule full market sync via APScheduler (hourly) to keep local DB current
- For authenticated endpoints (placing orders, v2), use PolyMarkets signature-based auth
## Brier Score Calculation
- **scikit-learn** provides `brier_score_loss(y_true, y_prob)` — use for single-outcome calculations
- For batch calculations (leaderboard), implement directly: `np.mean((predictions - outcomes) ** 2)` — simpler and avoids sklearn dependency overhead
- For the leaderboard, sort by ascending Brier Score (lower = better, 0 = perfect)
- Consider tracking: mean Brier Score, median, and per-model breakdown
## Sources
- **FastAPI docs** (https://fastapi.tiangolo.com/) — Lifespan event patterns, APScheduler integration (verified)
- **OpenRouter docs** (https://openrouter.ai/docs) — API format, Python SDK, rate limits, model variants (verified)
- **Tavily docs** (https://docs.tavily.com/) — API endpoints, Python SDK, parameters, async support (verified)
- **PyPI: openrouter 0.8.1** — Official Python SDK (verified)
- **PyPI: tavily-python 0.7.23** — Official Python SDK (verified)
- **PyPI: FastAPI 0.135.3** — Current version (verified)
- **PyPI: SQLAlchemy 2.0.49** — Current version (verified)
- **PyPI: SQLModel 0.0.38** — Current version (verified)
- **PyPI: asyncpg 0.31.0** — Current version (verified)
- **PyPI: APScheduler 3.11.2** — Stable version, 4.x is pre-release (verified via GitHub)
- **PyPI: PyJWT 2.12.1** — Current version (verified)
- **PyPI: httpx 0.28.1** — Current version (verified)
- **PyPI: uvicorn 0.44.0** — Current version (verified)
- **PyPI: Pydantic 2.12.5** — Current version with v2 features (verified)
- **PyPI: Alembic 1.18.4** — Current version (verified)
- **PyPI: ruff 0.15.10** — Current version (verified)
- **PyPI: pytest-asyncio 1.3.0** — Current version (verified)
- **PyPI: bcrypt 5.0.0** — Current version (verified)
- **PyPI: passlib 1.7.4** — Current version (verified)
- **GitHub: agronholm/apscheduler** — APScheduler 3.x stable, 4.x pre-release warning (verified)
<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->
## Conventions

Conventions not yet established. Will populate as patterns emerge during development.
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->
## Architecture

Architecture not yet mapped. Follow existing patterns found in the codebase.
<!-- GSD:architecture-end -->

<!-- GSD:skills-start source:skills/ -->
## Project Skills

No project skills found. Add skills to any of: `.claude/skills/`, `.agents/skills/`, `.cursor/skills/`, or `.github/skills/` with a `SKILL.md` index file.
<!-- GSD:skills-end -->

<!-- GSD:workflow-start source:GSD defaults -->
## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd-quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd-debug` for investigation and bug fixing
- `/gsd-execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->



<!-- GSD:profile-start -->
## Developer Profile

> Profile not yet configured. Run `/gsd-profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
