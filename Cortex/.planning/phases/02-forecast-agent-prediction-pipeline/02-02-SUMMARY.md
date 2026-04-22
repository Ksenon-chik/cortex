---
plan: 02-02
status: completed
---

# Сводка Плана 02-02: Forecast Endpoint

## Что было сделано

### Задача 1: Схемы Forecast + POST /forecast endpoint
- Создан `backend/app/schemas/forecast.py` с `ForecastRequest` (event_id: UUID, model: str) и `ForecastResponse` (model_name, probability, verdict, reasoning, sources, confidence_score, created_at)
- Создан `backend/app/routers/forecasts.py` с `POST /api/forecast` endpoint, который:
  - Валидирует модель по `settings.available_models` (400 если неверная)
  - Ищет событие по ID (404 если не найдено)
  - Создаёт экземпляр `PredictionAgent` для каждого запроса
  - Вызывает `agent.generate_forecast()` с контекстом события
  - Сохраняет запись `Prediction` в базу данных
  - Возвращает `ForecastResponse`
  - Перехватывает исключения и возвращает 500 с универсальным сообщением
- Подключён forecast маршрутизатор в `backend/app/main.py` с префиксом `/api/forecast`

### Задача 2: Интеграционные тесты
- Создан `backend/tests/test_forecast.py` с 5 тестами:
  - `test_generate_forecast_success` — валидный запрос возвращает 200 с корректными данными
  - `test_generate_forecast_event_not_found` — отсутствующее событие возвращает 404
  - `test_generate_forecast_invalid_model` — неизвестная модель возвращает 400
  - `test_generate_forecast_invalid_event_id_format` — некорректный UUID возвращает 422
  - `test_forecast_stored_in_database` — прогноз сохраняется после запроса

## Ключевые решения
- **OpenRouter SDK**: Пакет `openrouter` (v0.8.1) использует класс `OpenRouter` с явным параметром `async_client=httpx.AsyncClient()`, а не `AsyncOpenRouter`. Обновлён `forecast.py` соответственно.
- **SQLite для тестирования**: PostgreSQL недоступен локально. Заменён `postgresql.JSONB` на общий `JSON` в `conftest.py` для совместимости с SQLite.
- **Общая БД-сессия**: Тесты используют общую сессию (обёрнутую в rollback транзакции), чтобы фикстуры вроде `sample_event` были видны запросам БД endpoint.
- **Исправление дубликата индекса**: `Event.category` имел `index=True` + явный `Index("ix_events_category", ...)` в `__table_args__`, что вызывало дублирование индексов. Удалён `index=True` из столбца.

## Верификация
- Все 12 тестов проходят (7 agent + 5 forecast)
- Ruff lint проходит (предупреждения E501 о длине строк уже существуют в кодовой базе)
- Импорт модулей проверен

## addressed требования
- FC-01: Пользователь может отправить запрос прогноза и получить вероятность, обоснование, источники
