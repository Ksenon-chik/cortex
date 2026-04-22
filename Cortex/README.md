# Cortex

Cortex — full-stack платформа для прогнозирования событий Polymarket с журналом прогнозов, таблицей лидеров и пользовательским подключением API-ключей для LLM-провайдеров.

Сейчас проект уже не находится в стадии «чистой идеи»: в репозитории есть рабочий backend на FastAPI, frontend на Next.js, административный контур, ручной импорт событий из Polymarket, генерация прогнозов через несколько провайдеров и расчёт Brier Score после резолюции рынков.

---

## Что умеет проект сейчас

- Просмотр событий Polymarket с поиском, фильтрацией по категориям и отдельной страницей события
- Генерация прогноза по событию через SSE-поток с логами выполнения
- Хранение истории прогнозов по каждому событию и сравнение моделей по точности
- Таблица лидеров моделей по рассчитанному `brier_score`
- Регистрация, логин, refresh-сессии, профиль пользователя
- BYOK-подключение пользовательских API-ключей для AI-провайдеров
- Админ-панель для пользователей, моделей, событий и служебных операций с базой
- Ручной поиск событий в Polymarket, импорт, повторная синхронизация и удаление событий
- Фоновая проверка резолюции рынков и обновление точности прогнозов

---

## Текущая архитектура

```text
Frontend (Next.js App Router)
    -> /api/* proxy route
Backend (FastAPI)
    -> auth / events / forecast / admin / user API routers
    -> forecast orchestration + Tavily search + selected LLM provider
    -> APScheduler hourly resolution job
    -> PostgreSQL
```

### Backend

Основные зоны ответственности:

- `backend/app/routers/auth.py` — регистрация, логин, logout, refresh, `me`
- `backend/app/routers/events.py` — список событий, категории, карточка события
- `backend/app/routers/forecasts.py` — список моделей, поток генерации прогноза, журнал прогнозов, leaderboard
- `backend/app/routers/admin.py` — пользователи, модели, Polymarket import/resync, db tools
- `backend/app/routers/user_api_keys.py` — CRUD для пользовательских API-ключей
- `backend/app/services/forecasting.py` и смежные сервисы — оркестрация генерации прогноза
- `backend/app/services/resolution.py` — закрытие событий и расчёт Brier Score
- `backend/app/scheduler.py` — регистрация фоновых задач

### Frontend

Ключевые страницы:

- `frontend/app/page.tsx` — лендинг
- `frontend/app/events/page.tsx` — лента событий
- `frontend/app/events/[id]/page.tsx` — карточка события и `Generate Forecast`
- `frontend/app/leaderboard/page.tsx` — рейтинг моделей
- `frontend/app/profile/page.tsx` — профиль и пользовательские API-ключи
- `frontend/app/admin/page.tsx` — админка
- `frontend/app/api/[[...path]]/route.ts` — прокси на backend

---

## Поставщики моделей

Сейчас в проекте поддержана работа с пользовательскими API-ключами для следующих провайдеров:

- OpenRouter
- Google
- Groq
- DeepSeek
- Mistral
- Cerebras
- Fireworks
- NVIDIA
- Tavily используется отдельно как провайдер веб-поиска

Важно: генерация прогноза строится вокруг пользовательских ключей. Это значит, что доступность конкретной модели зависит от того, подключил ли пользователь соответствующий API-ключ и активна ли модель в админке.

---

## Как сейчас устроен поток событий

1. Администратор ищет рынки Polymarket через админ-панель
2. Нужные события импортируются вручную в локальную БД
3. Пользователь открывает событие и запускает `Generate Forecast`
4. Backend делает исследование, обращается к выбранному провайдеру и сохраняет прогноз
5. Фоновая задача периодически проверяет, не разрешился ли рынок
6. После резолюции backend обновляет `events.closed`, `events.resolved_outcome` и считает `brier_score` для прогнозов

Это важно для документации: сейчас проект не синхронизирует автоматически весь Polymarket-каталог каждый час. Автоматически работает именно проверка резолюции уже сохранённых событий.

---

## Схема данных высокого уровня

### `events`

Хранит импортированные рынки Polymarket.

Ключевые поля:
- `polymarket_market_id`
- `title`
- `description`
- `category`
- `category_normalized`
- `outcomes`
- `outcome_prices`
- `active`
- `closed`
- `end_date`
- `resolved_outcome`

### `predictions`

Хранит прогнозы моделей по событиям.

Ключевые поля:
- `event_id`
- `model_name`
- `probability`
- `verdict`
- `sources`
- `reasoning`
- `confidence_score`
- `brier_score`
- `user_id`

### `users`

Хранит учётные записи и флаги доступа.

Ключевые поля:
- `email`
- `plan`
- `is_active`
- `whitelisted`
- `is_admin`

### `user_api_keys`

Хранит пользовательские API-ключи провайдеров.

Ключевые поля:
- `user_id`
- `provider`
- `api_key`

---

## Важные текущие ограничения

- Вайтлист-флаг присутствует в данных и админке, но не является полноценным обязательным барьером для всех защищённых сценариев
- Премиум-план сейчас влияет в первую очередь на лимиты прогнозов, а не на отдельную систему premium-only моделей
- API-ключи пользователей сейчас хранятся в базе в открытом виде — это нужно считать временным техническим долгом
- Импорт событий из Polymarket ручной, а не полный автоматический каталог
- В репозитории присутствуют локальные артефакты окружения и сборки; перед production-hardening их стоит вычистить

---

## API overview

### Auth

- `POST /api/auth/register`
- `POST /api/auth/login`
- `POST /api/auth/logout`
- `POST /api/auth/refresh`
- `GET /api/auth/me`

### Events

- `GET /api/events`
- `GET /api/events/categories`
- `GET /api/events/{event_id}`

### Forecast

- `GET /api/forecast/models`
- `GET /api/forecast/{event_id}/predictions`
- `GET /api/forecast/stream`
- `GET /api/forecast/leaderboard`

### User API keys

- `GET /api/user/api-keys`
- `POST /api/user/api-keys`
- `DELETE /api/user/api-keys/{provider}`

### Admin

- `GET /api/admin/users`
- `POST /api/admin/users/{user_id}/approve`
- `POST /api/admin/users/{user_id}/promote`
- `POST /api/admin/users/{user_id}/plan`
- `GET /api/admin/models`
- `POST /api/admin/models`
- `PATCH /api/admin/models/{model_id}`
- `DELETE /api/admin/models/{model_id}`
- `GET /api/admin/polymarket/search`
- `POST /api/admin/events/add/{market_id}`
- `POST /api/admin/events/resync/{event_id}`
- `DELETE /api/admin/events/{event_id}`
- `POST /api/admin/events/truncate`
- `GET /api/admin/db-size`
- `POST /api/admin/backfill-categories`

---

## Технологии

| Layer | Technology |
|---|---|
| Backend | Python 3.12, FastAPI, SQLAlchemy async, Alembic |
| Database | PostgreSQL |
| Scheduler | APScheduler |
| HTTP clients | httpx |
| Frontend | Next.js 14, React 18, TypeScript, Tailwind |
| Data/UI | TanStack Query, TanStack Table, React Hook Form, Zod |
| AI/Search | user-provided provider APIs + Tavily |
| Auth | JWT + httpOnly cookies |

---

## Локальный запуск

### Backend

```bash
cd backend
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

### Frontend

```bash
cd frontend
pnpm install
pnpm dev
```

### Через Docker Compose

В репозитории есть `docker-compose.yml` и Dockerfile'ы для локальной среды/деплоя, но актуальный сценарий разработки всё равно проще поддерживать отдельным запуском backend и frontend.

---

## Переменные окружения

### Backend

Минимальный набор зависит от сценария, но обычно нужны:

```env
DATABASE_URL=postgresql+asyncpg://...
JWT_SECRET_KEY=...
TAVILY_API_KEY=...
POLYMARKET_API_URL=...
CORS_ORIGINS=http://localhost:3000
```

Также используются настройки лимитов, cookie/JWT и конфигурация провайдеров.

### Frontend

```env
BACKEND_URL=http://localhost:8000
```

Frontend работает через server-side proxy route, поэтому публичный `NEXT_PUBLIC_API_URL` ему не требуется.

---

## Что стоит делать дальше

Если смотреть на проект как на продукт, ближайшие технические кандидаты на доработку такие:

- зашифровать пользовательские API-ключи в БД
- довести whitelist до полного enforcement
- отделить premium-доступ к моделям от общего quota bypass
- вычистить из репозитория build/runtime артефакты
- добавить более системные документы по деплою, резервному копированию и мониторингу
