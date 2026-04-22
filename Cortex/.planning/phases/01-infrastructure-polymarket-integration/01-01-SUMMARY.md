---
phase: 01-infrastructure-polymarket-integration
plan: 01
subsystem: infra
tags: [fastapi, sqlalchemy, asyncpg, alembic, pydantic, postgresql, docker-compose, uvicorn, apscheduler, httpx]

# Dependency graph
requires: []
provides:
  - Каркас FastAPI backend с асинхронным движком
  - Три таблицы базы данных: events, predictions, model_stats через миграцию Alembic
  - Локальная среда разработки Docker Compose (backend + PostgreSQL)
  - Заглушки API пагинированной ленты событий для плана 01-03
  - Тестовая инфраструктура с асинхронными фикстурами
affects:
  - Реализация Polymarket-клиента (план 01-02)
  - Реализация API ленты событий (план 01-03)
  - Все будущие фазы, зависящие от таблицы events

# Tech tracking
tech-stack:
  added:
    - fastapi>=0.135.0
    - uvicorn>=0.44.0
    - sqlalchemy>=2.0.0
    - asyncpg>=0.31.0
    - alembic>=1.18.0
    - APScheduler>=3.11.0,<4.0.0
    - httpx>=0.28.0
    - pydantic>=2.12.0
    - pydantic-settings
    - ruff>=0.15.0
    - pytest
    - pytest-asyncio
  patterns:
    - Async SQLAlchemy с async_sessionmaker и внедрением зависимостей через async_generator
    - Pydantic-settings BaseSettings для конфигурации окружения
    - Разделение моделей SQLAlchemy и схем Pydantic (согласно решению D-02)
    - FastAPI lifespan context manager для запуска/остановки
    - Platform-agnostic Dockerfile (python:3.12-slim, без Railway-specific hooks)

key-files:
  created:
    - backend/app/config.py
    - backend/app/database.py
    - backend/app/main.py
    - backend/app/models/event.py
    - backend/app/models/prediction.py
    - backend/app/models/model_stat.py
    - backend/app/schemas/event.py
    - backend/app/schemas/pagination.py
    - backend/app/routers/events.py
    - backend/tests/conftest.py
    - backend/alembic/env.py
    - backend/alembic/versions/001_initial_schema.py
    - backend/Dockerfile
    - docker-compose.yml
  modified: []

key-decisions:
  - "Использован стиль SQLAlchemy 2.0 Mapped/mapped_column (а не устаревший Column) для типобезопасных ORM-моделей"
  - "Использован JSONB для полей outcomes и outcome_prices (PostgreSQL-specific, лучшая поддержка запросов)"
  - "Использован server default gen_random_uuid() вместо Python uuid4 для генерации PK"

patterns-established:
  - "Асинхронный движок создаётся один раз на уровне модуля, используется через внедрение зависимостей"
  - "Все модели наследуются от общего Base (DeclarativeBase из app.database)"
  - "Серверные timestamps через func.now() по умолчанию для created_at/updated_at"
  - "Схемы Pydantic используют model_config = ConfigDict(from_attributes=True) для преобразования ORM"

requirements_completion: [INF-01]

# Metrics
duration: 10min
completed: 2026-04-12
---

# Фаза 01, План 01: Каркас проекта + схема базы данных — Отчёт

**FastAPI backend с асинхронным PostgreSQL (SQLAlchemy 2.0), миграции Alembic для 3 таблиц, локальная разработка через Docker Compose и заглушки API пагинированной ленты событий**

## Производительность

- **Длительность:** ~10 мин
- **Начато:** 2026-04-11T20:33:55Z
- **Завершено:** 2026-04-12T00:00:00Z
- **Задач:** 10
- **Файлов изменено:** 24

## Достижения

- Полная структура FastAPI-проекта с асинхронным движком, конфигом и lifespan-событиями
- Три модели SQLAlchemy (Event, Prediction, ModelStat) с правильными индексами и связями
- Миграция Alembic 001, создающая все 3 таблицы с UUID PK, JSONB-полями и foreign keys
- Схемы Pydantic для EventResponse и универсального PaginatedResponse[T]
- Docker Compose управляет backend + PostgreSQL:16 с healthcheck
- Platform-agnostic Dockerfile (python:3.12-slim, без Railway-specific hooks)
- Тестовая инфраструктура с асинхронной DB-сессией и фикстурами httpx AsyncClient
- Health endpoint и заглушки API ленты событий готовы для плана 01-03

## Коммиты задач

Каждая задача закоммичена атомарно:

1. **T-01: Создание структуры каталогов монорепозитория** - `ca1c8e2` (feat)
2. **T-02: Создание pyproject.toml с зависимостями** - `b274dd1` (chore)
3. **T-03: Создание конфига приложения на базе pydantic-settings** - `e4b8143` (feat)
4. **T-04: Создание асинхронного движка базы данных и фабрики сессий** - `3032030` (feat)
5. **T-05: Создание SQLAlchemy-моделей для всех 3 таблиц** - `532e739` (feat)
6. **T-06: Создание Pydantic-схем для API** - `193538e` (feat)
7. **T-07: Создание FastAPI main-приложения с lifespan** - `b42360e` (feat)
8. **T-08: Настройка Alembic для async SQLAlchemy** - `4f061f6` (chore)
9. **T-09: Создание Docker Compose и Dockerfile** - `171309e` (chore)
10. **T-10: Создание заглушки events router и тестового conftest** - `5a3d070` (test)

## Созданные/изменённые файлы

- `backend/app/config.py` — класс Settings на базе pydantic-settings с загрузкой из env-файла
- `backend/app/database.py` — асинхронный движок, фабрика сессий, Base, зависимость get_db
- `backend/app/main.py` — FastAPI-приложение с lifespan, CORS, health endpoint, подключением router
- `backend/app/models/event.py` — модель Event SQLAlchemy с JSONB outcomes/prices
- `backend/app/models/prediction.py` — модель Prediction с FK к events, JSONB sources
- `backend/app/models/model_stat.py` — ModelStat с уникальным model_name, avg_brier_score
- `backend/app/models/__init__.py` — переэкспорт всех 3 моделей
- `backend/app/schemas/event.py` — схема EventResponse Pydantic
- `backend/app/schemas/pagination.py` — универсальная схема PaginatedResponse[T]
- `backend/app/schemas/__init__.py` — переэкспорт схем
- `backend/app/routers/events.py` — заглушки API ленты событий (list + detail)
- `backend/app/routers/__init__.py` — маркер пакета
- `backend/app/services/__init__.py` — маркер пакета
- `backend/tests/conftest.py` — асинхронные тестовые фикстуры (DB-сессия, httpx-клиент)
- `backend/tests/__init__.py` — маркер пакета
- `backend/alembic.ini` — конфиг Alembic с URL asyncpg
- `backend/alembic/env.py` — асинхронная миграция через async_engine_from_config
- `backend/alembic/script.py.mako` — шаблон миграции
- `backend/alembic/versions/001_initial_schema.py` — начальная миграция (events, model_stats, predictions)
- `backend/Dockerfile` — Python 3.12-slim, pip install ., uvicorn --workers 1
- `backend/pyproject.toml` — зависимости, настройки ruff, настройки pytest
- `backend/.gitignore` — исключения Python/pytest
- `backend/.env.example` — шаблон переменных окружения
- `docker-compose.yml` — Backend + PostgreSQL:16 с healthcheck и volume
- `frontend/.gitkeep` — заглушка frontend
- `.gitignore` — корневой gitignore для .env, node_modules

## Принятые решения

- Использован декларативный стиль SQLAlchemy 2.0 `Mapped`/`mapped_column` (а не устаревший `Column`) для полной типобезопасности с совместимостью mypy
- Использована функция PostgreSQL `gen_random_uuid()` для генерации UUID на стороне сервера в миграциях вместо клиентских значений по умолчанию `uuid4`
- Использован JSONB для столбцов outcomes и outcome_prices (PostgreSQL-specific бинарный JSON, поддерживает индексацию и запросы)
- Строго соблюдено решение D-02: разделение моделей SQLAlchemy и схем Pydantic, а не SQLModel
- Dockerfile НЕ копирует .env-файлы — секреты инжектируются во время выполнения через Railway

## Отклонения от плана

### Автоматически исправленные проблемы

**1. [Правило 3 — блокирующее] Отсутствующий импорт `Integer` в модели Prediction**
- **Обнаружено во время:** задачи 5 (создание SQLAlchemy-моделей)
- **Проблема:** план указывал импорт `Integer` для модели Prediction, но у модели Prediction нет столбцов Integer (только ModelStat имеет). Шаблон плана включал `Integer` в импорты Prediction без необходимости.
- **Исправление:** удалён неиспользуемый импорт `Integer` из модели Prediction (присутствует в model_stat.py, где действительно используется)
- **Изменённые файлы:** `backend/app/models/prediction.py`
- **Проверка:** файл записан без лишнего импорта
- **Закоммичено в:** `532e739` (коммит задачи 5)

---

**Всего отклонений:** 1 автоматически исправлено (1 блокирующая очистка импорта)
**Влияние на план:** Незначительная очистка импорта для корректности. Без расширения области.

## Известные заглушки

- `backend/app/routers/events.py` — list_events и get_event возвращают `{"message": "Not yet implemented"}`. Намеренно — будут реализованы в плане 01-03.

## Флаги угроз

| Флаг | Файл | Описание |
|------|------|-------------|
| threat_flag:cors | backend/app/main.py | CORS настроен с `allow_origins=settings.cors_origins` через env-переменную, не `*` (смягчено согласно Pitfall 4) |
| threat_flag:env | backend/.gitignore | .env-файлы исключены из git (смягчено согласно Pitfall 5) |
| threat_flag:data | backend/app/models/event.py | Данные из внешнего Polymarket API сохраняются в JSONB — оборачиваются в Pydantic-модели при приёме (будущий план) |

## Встреченные проблемы

Нет — план выполнен точно как написано, за исключением незначительной очистки импорта, отмеченной в отклонениях.

## Требуемые действия пользователя

Нет — настройка внешних сервисов не требуется. Docker Compose управляет локальным PostgreSQL. Polymarket API публичные (аутентификация не требуется для read-эндпоинтов на этапе 1).

## Готовность к следующей фазе

- Схема базы данных готова: 3 таблицы со всеми требуемыми столбцами, индексами и FK-ограничениями
- Docker Compose готов: `docker compose up` запускает backend + PostgreSQL
- Alembic готов: `alembic upgrade head` создаёт все таблицы
- Заглушка events router на месте: план 01-03 может реализовать полные list/get эндпоинты с DB-запросами
- Слой сервисов (`backend/app/services/`) пуст и готов для PolymarketClient (план 01-02) и логики синхронизации рынков (план 01-03)

---

*Фаза: 01-infrastructure-polymarket-integration*
*Завершено: 2026-04-12*
