# Stack Snapshot

## Backend

- Python 3.12
- FastAPI
- SQLAlchemy async
- asyncpg
- Alembic
- APScheduler
- httpx
- Pydantic / pydantic-settings
- PyJWT
- bcrypt
- tavily-python
- openrouter SDK и провайдерские HTTP-интеграции

## Frontend

- Next.js 14
- React 18
- TypeScript
- Tailwind CSS
- TanStack Query
- TanStack Table
- React Hook Form
- Zod
- Recharts
- Lucide React

## Database

- PostgreSQL

## Deployment assumptions

- Backend и frontend собираются отдельно
- Frontend ходит в backend через proxy route
- Scheduler крутится внутри backend-приложения
- Для безопасной работы scheduler желательно избегать бесконтрольного multi-worker режима

## Что важно не путать

- В проекте используется SQLAlchemy async, а не SQLModel
- JWT-слой построен вокруг PyJWT, а не `python-jose`
- BYOK и multi-provider support уже часть текущего продукта, а не будущая идея
- Главный автоматический фоновой процесс сейчас — resolution job, а не полный Polymarket sync
