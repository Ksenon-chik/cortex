# Phase 1: Infrastructure + Polymarket Integration - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-11
**Phase:** 01-infrastructure-polymarket-integration
**Areas discussed:** Project Structure, ORM & Models, Polymarket API, Database Schema, Migrations, API Style

---

## Project Structure

| Option | Description | Selected |
|--------|-------------|----------|
| Минимальная (плоская) | Всё в одной папке app/: main.py, models.py, schemas.py, routers/, services/. Просто для одного разработчика. | |
| Модульная (по доменам) | Папки по доменам: app/events/, app/scheduler/, app/polymarket/. Масштабируется, но больше boilerplate. | |
| Монорепозиторий сразу | backend/ + frontend/ папки уже сейчас. Frontend будет пустой пока. Зато Docker Compose сразу охватывает всё. | ✓ |

**User's choice:** Монорепозиторий сразу (backend/ + frontend/)
**Notes:** Пользователь хочет всё в одном репозитории на GitHub с автодеплоем на Railway, с возможностью будущего переезда на render.com. Dockerfile должен быть platform-agnostic.

## ORM & Models

| Option | Description | Selected |
|--------|-------------|----------|
| SQLModel (рекомендуется) | Одна модель = ORM + Pydantic + FastAPI тип. Меньше бойлерплейта, уже выбран в исследовании. | |
| SQLAlchemy + Pydantic отдельно | Классический подход. Больше кода, но более зрелая экосистема и документация. | ✓ |

**User's choice:** SQLAlchemy + Pydantic отдельно
**Notes:** Пользователь предпочёл зрелую экосистему SQLAlchemy вместо удобства SQLModel.

## Polymarket API

| Option | Description | Selected |
|--------|-------------|----------|
| CLOB + Gamma (рекомендуется) | CLOB API для активных рынков + Gamma API для резолюций. Как рекомендовано в исследовании. | ✓ |
| Только CLOB API | Один источник для всего. Проще, но может не хватать данных о резолюциях. | |
| Скрапинг + API | Комбинировать API с парсингом HTML для надёжности. Больше работы, но устойчивее к изменениям API. | |

**User's choice:** CLOB + Gamma (рекомендуется)

## Database Schema

| Option | Description | Selected |
|--------|-------------|----------|
| Минимальная (1 таблица) | Только events. Прогнозы и модели появятся в фазе 2. Меньше миграций сейчас. | |
| Полная (3 таблицы) | events + predictions + model_stats сразу. Foreign keys работают с самого начала, меньше миграций потом. | ✓ |

**User's choice:** Полная (3 таблицы)

## Migrations

| Option | Description | Selected |
|--------|-------------|----------|
| Alembic (рекомендуется) | Стандарт для SQLAlchemy. Автогенерация миграций из моделей, откат миграций. Railway совместим. | ✓ |
| SQLModel + Alembic | SQLModel поверх SQLAlchemy с Alembic. Чуть проще синтаксис, но та же база. | |

**User's choice:** Alembic (рекомендуется)

## API Style

| Option | Description | Selected |
|--------|-------------|----------|
| REST (рекомендуется) | Простые endpoint'ы: GET /events, GET /events/{id}. Легко документировать, легко деплоить. | ✓ |
| GraphQL | Один endpoint, клиент запрашивает нужные поля. Больше setup, но гибче для фронтенда. | |

**User's choice:** REST (рекомендуется)

---

## Claude's Discretion

Области, где пользователь оставил решение на усмотрение:
- Exact connection pool sizing
- Polymarket CLOB API endpoint paths (verify at runtime)
- Exact Pydantic model field names
- Dockerfile base image choice

## Deferred Ideas

None — discussion stayed within phase scope.
