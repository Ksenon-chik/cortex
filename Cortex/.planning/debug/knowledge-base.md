# GSD Debug Knowledge Base

Разрешённые debug-сессии. Используются `gsd-debugger` для выдачи гипотез по известным паттернам в начале новых расследований.

---

## auth-404-prod — Auth-эндпоинты возвращают 404 на Railway, куки не устанавливаются
- **Дата:** 2026-04-12
- **Паттерны ошибок:** 404 на auth эндпоинтах, куки не ставятся, CORS preflight failure
- **Корневая причина:** (1) Отсутствие reverse proxy между фронтендом и бэкендом на отдельных Railway доменах — CORS preflight fails, браузер блокирует запросы, что выглядит как 404. (2) cookie_domain по умолчанию — пустая строка "" вместо None — куки привязаны только к хосту бэкенда, не видны домену фронтенда. (3) env var CORS_ORIGINS как строка JSON-массива не парсится pydantic-settings без валидатора.
- **Фикс:** (1) Добавлены Next.js rewrites для проксирования /api/* на бэкенд, полностью устраняя CORS. Обновлён API-клиент фронтенда на относительные пути. (2) Добавлен валидатор parse_cors_origins для десериализации строк JSON-массива. (3) Изменён cookie_domain с str = "" на Optional[str] = None.
- **Изменённые файлы:** frontend/next.config.mjs, frontend/lib/api.ts, backend/app/config.py
---

## events-bandwidth — Превышение лимита трафика Railway из-за выгрузки всех событий Polymarket при каждом поиске
- **Дата:** 2026-04-15
- **Паттерны ошибок:** Polymarket, search_markets, bandwidth, Railway, traffic limit, 5000 events, gamma API
- **Корневая причина:** search_markets() в polymarket.py загружала ВСЕ 5000+ активных маркетов с Gamma API при каждом запросе (while True loop с пагинацией по 100/page) перед клиентской фильтрацией. Открытие вкладки events в админке запускало полную загрузку каждый раз.
- **Фикс:** Добавлен in-memory кэш с TTL 5 минут в PolymarketClient. Первый поиск загружает все маркеты и кеширует, последующие поиски в пределах TTL используют кеш без обращения к Polymarket API. Добавлен clear_markets_cache() для явной инвалидации.
- **Изменённые файлы:** backend/app/services/polymarket.py, backend/tests/test_services/test_polymarket.py
---
