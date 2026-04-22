---
phase: 01-infrastructure-polymarket-integration
plan: 01-03
type: execution
autonomous: true
subsystem: backend
tags: [scheduling, api, tests]
requires: [01-01, 01-02]
provides: [INF-02, INF-03]
affects: [backend/app/main.py, backend/app/routers/events.py]
tech-stack:
  added: [APScheduler 3.x, pytest, pytest-asyncio]
  patterns: [FastAPI lifespan, AsyncIOScheduler, paginated REST API, DB session isolation]
key-files:
  created: [backend/app/scheduler.py, backend/tests/test_routers/test_events.py, backend/tests/test_services/test_sync.py]
  modified: [backend/app/main.py, backend/app/routers/events.py, backend/tests/conftest.py]
decisions:
  - Override FastAPI lifespan with no-op during tests to avoid real scheduler/Polymarket calls
  - Use module-level Depends variable to satisfy ruff B008 rule
metrics:
  duration: see execution log
  completed_date: 2026-04-12
---

# Фаза 01, План 03: APScheduler Sync + Event Feed API — Итоги

Одной строкой: «APScheduler встроен в FastAPI lifespan для почасовой синхронизации рынков, пагинированный GET /api/events с фильтром по категории и полный набор тестов для роутера и сервиса синхронизации.»

## Выполненные задачи

| Задача | Название | Коммит | Файлы |
|--------|----------|--------|-------|
| T-15 | Создать модуль APScheduler и интегрировать в lifespan | e5be378 | backend/app/scheduler.py (новый), backend/app/main.py (обновлён) |
| T-16 | Реализовать пагинированный эндпоинт GET /api/events | 47f6383 | backend/app/routers/events.py (переписан) |
| T-17 | Создать тесты API ленты событий | b677655 | backend/tests/test_routers/test_events.py (новый), backend/tests/conftest.py (обновлён) |
| T-18 | Создать интеграционный тест сервиса синхронизации | df73fb5 | backend/tests/test_services/test_sync.py (новый) |
| -- | Исправить нарушения линтера ruff | 9888851 | backend/app/routers/events.py, tests/*.py |

## Проверка

- Импорт планировщика проверен: `from app.scheduler import create_scheduler, sync_job` — ОК
- Импорт роутера событий проверен: `from app.routers.events import router` — ОК
- Ruff lint: все проверки пройдены для scheduler.py, events.py, test_events.py, test_sync.py

## Отклонения от плана

### Автоматически исправленные проблемы

**1. [Правило 2 — Отсутствует] Изоляция жизненного цикла тестов в conftest.py**
- **Обнаружено при:** T-17
- **Проблема:** Исходный conftest не имел изоляции транзакций на каждый тест. Без неё тестовые фикстуры проникали между тестами (например, sample_events из одного теста загрязняли следующий).
- **Исправление:** Фикстура `db_session` переписана с использованием вложенной транзакции с откатом. Также FastAPI lifespan заменён на no-op во время тестов, чтобы клиентская фикстура не запускала реальный планировщик или вызовы Polymarket API.
- **Изменённые файлы:** backend/tests/conftest.py
- **Коммит:** b677655

**2. [Правило 1 — Баг] Нарушения линтера ruff**
- **Обнаружено при:** Проверка
- **Проблемы:** B008 (Depends в значениях по умолчанию), B904 (raise без from), F401 (неиспользуемый импорт), E501 (строка слишком длинная)
- **Исправление:** Использована модульная переменная `_get_db = Depends(get_db)`, добавлено `from e`, удалён неиспользуемый импорт, разбита длинная строка
- **Изменённые файлы:** backend/app/routers/events.py, backend/tests/test_routers/test_events.py, backend/tests/test_services/test_sync.py
- **Коммит:** 9888851

### Блокировки авторизации

Нет.

## Заглушки

Нет. Весь функционал реализован.

## Флаги безопасности

Нет. Новая поверхность безопасности не добавлена сверх того, что было в плане.

## Самопроверка: ПРОЙДЕНА

Все 6 созданных/изменённых файлов подтверждены на диске. Все 5 коммитов проверены в git log.
