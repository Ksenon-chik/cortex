---
plan: 02-03
status: completed
---

# Сводка Плана 02-03: Список моделей + Журнал прогнозов

## Что было сделано

### Задача 1: Новые схемы + endpoints
Расширен `backend/app/schemas/forecast.py`:
- `AvailableModel` — id, name, tier
- `AvailableModelsResponse` — список AvailableModel
- `PredictionJournalEntry` — id, model_name, probability, verdict, reasoning, sources, created_at
- `PredictionJournalResponse` — список PredictionJournalEntry

Расширен `backend/app/routers/forecasts.py`:
- `GET /api/forecast/models` — возвращает доступные модели с человеко-читаемыми именами из статического маппинга
- `GET /api/forecast/events/{event_id}/predictions` — возвращает журнал прогнозов для события, отсортированный по created_at desc, с 404 для неизвестных событий и 422 для неверного UUID

### Задача 2: Интеграционные тесты
Добавлено 6 тестов в `backend/tests/test_forecast.py`:
- `test_get_available_models` — валидирует форму ответа и tier="free"
- `test_get_available_models_matches_config` — валидирует по settings.available_models
- `test_get_event_predictions_empty` — пустой журнал возвращает []
- `test_get_event_predictions_with_data` — 2 прогноза возвращены с корректными полями
- `test_get_event_predictions_not_found` — неизвестное событие возвращает 404
- `test_get_event_predictions_invalid_uuid` — неверный формат UUID возвращает 422

## Ключевые решения
- **Путь маршрута**: Forecast маршрутизатор подключён на `/api/forecast`, поэтому endpoint прогнозов находится по адресу `/api/forecast/events/{event_id}/predictions` (а не `/api/events/{event_id}/predictions`, как изначально предполагалось в плане).
- **Типизация UUID**: Использован `event_id: uuid.UUID` в параметре пути, чтобы FastAPI автоматически валидировал и возвращал 422 для неверных форматов.
- **Пустой журнал**: Возвращает пустой список (не 404), когда событие существует, но не имеет прогнозов.

## Верификация
- Все 18 тестов проходят (7 agent + 11 forecast)
- Ruff lint проходит (E501 уже существует в кодовой базе)
- Импорт модулей проверен

## addressed требования
- FC-03: Пользователь может просмотреть список доступных бесплатных моделей перед отправкой прогноза
- FC-04: Пользователь может просмотреть журнал прогнозов для любого события
