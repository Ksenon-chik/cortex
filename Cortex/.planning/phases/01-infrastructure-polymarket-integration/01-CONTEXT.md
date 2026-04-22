# Фаза 1: Инфраструктура + интеграция с Polymarket — Контекст

**Собрано:** 2026-04-11
**Статус:** Готово к планированию

<domain>
## Граница фазы

Доставить работающий бэкенд на FastAPI с PostgreSQL, Docker Compose для локальной разработки, синхронизацию маркетов Polymarket через APScheduler (каждый час) и пагинированный REST API для ленты событий с фильтрацией по категориям. Без авторизации, без фронтенда, без прогнозиста — только события в базе данных и API для их запроса.

</domain>

<decisions>
## Решения по реализации

### Структура проекта
- **D-01:** Монорепозиторий с первого дня — директории `backend/` + `frontend/` в корне. Фронтенд создаётся пустым на Фазе 1, полностью заполняется на Фазе 5. Один GitHub-репозиторий, автодеплой на Railway, будущий переезд на render.com учтён в дизайне Dockerfile (без Railway-specific хуков).

### ORM и модели
- **D-02:** SQLAlchemy + Pydantic как отдельные слои (не SQLModel). SQLAlchemy-модели для ORM, отдельные Pydantic-схемы для валидации запросов/ответов API. Больше шаблонного кода, но более зрелая экосистема.
- **D-03:** Alembic для миграций БД — стандартный компаньон SQLAlchemy.

### Стиль API
- **D-04:** REST API — `GET /events` (пагинированный, фильтр по категории), `GET /events/{id}` (детали). Без GraphQL.

### Интеграция с Polymarket
- **D-05:** CLOB API для активных маркетов + Gamma API для разрешённых исходов. Все ответы обёрнуты в Pydantic-модели — падают громко при изменениях схемы. Экспоненциальный backoff на httpx-клиенте.
- **D-06:** APScheduler с `AsyncIOScheduler`, один воркер (`uvicorn --workers 1`). Идемпотентные upsert (не insert) для синхронизации маркетов.

### Схема БД
- **D-07:** Все 3 таблицы создаются с Фазы 1: `events`, `predictions`, `model_stats`. Foreign keys работают с начала, меньше миграций в будущем. Таблицы для predictions и model_stats будут пустыми до Фаз 2-3.

### Планировщик
- **D-08:** APScheduler 3.11.x (НЕ 4.x — пре-релиз, явно предупреждают). Встроен в lifespan-контекст FastAPI. Ежечасная задача синхронизации маркетов.

### На усмотрение Claude
- Точный размер пула соединений (в разумных пределах)
- Пути эндпоинтов Polymarket CLOB API (проверять при выполнении — они меняются)
- Точные имена полей Pydantic-моделей (следовать схеме ответа Polymarket)
- Базовый образ Dockerfile (python:3.12-slim или аналог)

</decisions>

<canonical_refs>
## Канонические ссылки

### Инфраструктура
- `.planning/ROADMAP.md` — цель Фазы 1, планы, критерии успеха
- `.planning/REQUIREMENTS.md` — требования INF-01, INF-02, INF-03
- `.planning/research/SUMMARY.md` — рекомендации стека, ограничения версий
- `.planning/research/ARCHITECTURE.md` — системная архитектура, границы компонентов, поток данных
- `.planning/research/PITFALLS.md` — подводные камни #3 (воркеры APScheduler), #7 (пул БД), #9 (CORS), #10 (утечки env)

### Polymarket
- `.planning/research/SUMMARY.md` §Polymarket CLOB API — заметки о нестабильности API, проверить на момент реализации

</canonical_refs>

<code_context>
## Существующий код

### Переиспользуемые активы
- Нет — проект с нуля, нет кода кроме README.md и CLAUDE.md

### Устоявшиеся паттерны
- Conventional commits (из ограничений PROJECT.md)
- async/await повсюду (из ограничений PROJECT.md)
- Pydantic v2 (из ограничений PROJECT.md)

### Точки интеграции
- Docker Comorchestrates бэкенд + PostgreSQL локально
- Lifespan FastAPI запускает/останавливает APScheduler
- Деплой на Railway использует переменные окружения (без закоммиченных .env-файлов)

</code_context>

<specifics>
## Конкретные идеи

- "Хочу всё в одном репозитории на GitHub и автодеплой на Railway, но с возможностью переезда на render.com" — Dockerfile должен быть platform-agnostic, без Railway-specific хуков
- Все 3 таблицы (events, predictions, model_stats) создаются сразу — foreign keys работают с начала

</specifics>

<deferred>
## Отложенные идеи

Нет — обсуждение осталось в рамках фазы.

</deferred>

---

*Фаза: 01-infrastructure-polymarket-integration*
*Контекст собран: 2026-04-11*
