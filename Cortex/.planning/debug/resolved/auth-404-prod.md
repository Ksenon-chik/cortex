---
status: awaiting_human_verify
trigger: "auth endpoints return 404 on production (Railway), cookies not being set"
created: "2026-04-12T00:00:00+00:00"
updated: "2026-04-12T00:30:00+00:00"
---

## Текущий фокус
hypothesis: ФИКСЫ ПРИМЕНЕНЫ — (1) Добавлены Next.js rewrites для проксирования /api/* на бэкенд, полностью устраняя CORS. (2) Добавлен парсер JSON-массива для env var CORS_ORIGINS. (3) Изменён дефолт cookie_domain с "" на None.
test: Ожидает проверки пользователем на Railway
expecting: Запросы авторизации успешны, куки устанавливаются корректно
next_action: await_human_verify

## Симптомы

expected: Авторизация должна работать — куки устанавливаются, эндпоинты auth доступны
actual: Эндпоинты авторизации возвращают 404, куки не ставятся
errors: 404 на auth endpoints
reproduction: Попытка авторизации через фронтенд на https://cortex-info.up.railway.app или напрямую через API
started: Никогда не работала в продакшене, это первая настройка

## Исключено

- hypothesis: Auth-маршруты не зарегистрированы в FastAPI app
  evidence: main.py line 91: app.include_router(auth_router, prefix="/api/auth", tags=["auth"]) — маршруты ЗАРЕГИСТРИРОВАНЫ на /api/auth/*
  timestamp: 2026-04-12T00:15:00+00:00

- hypothesis: Фронтенд вызывает неверный URL-путь
  evidence: frontend/lib/api.ts вызывает /api/auth/login, /api/auth/register — пути точно совпадают с маршрутами бэкенда
  timestamp: 2026-04-12T00:15:00+00:00

## Доказательства

- timestamp: 2026-04-12T00:10:00+00:00
  checked: backend/app/routers/auth.py
  found: Auth-маршруты определены как /register, /login, /logout, /refresh, /me — без префикса в самом роутере
  implication: Это стандартные FastAPI маршруты, префикс добавляется при подключении

- timestamp: 2026-04-12T00:10:00+00:00
  checked: backend/app/main.py line 91
  found: app.include_router(auth_router, prefix="/api/auth", tags=["auth"])
  implication: Полные auth-пути: /api/auth/register, /api/auth/login, /api/auth/logout, /api/auth/refresh, /api/auth/me

- timestamp: 2026-04-12T00:12:00+00:00
  checked: frontend/lib/api.ts
  found: API_BASE = process.env.NEXT_PUBLIC_API_URL || ""; полный URL = API_BASE + path
  implication: В продакшене NEXT_PUBLIC_API_URL=https://cortex-production-f79a.up.railway.app, значит auth-вызовы идут на https://cortex-production-f79a.up.railway.app/api/auth/login

- timestamp: 2026-04-12T00:13:00+00:00
  checked: frontend/next.config.mjs
  found: Rewrites не настроены. Только output: "standalone".
  implication: Нет reverse proxy от фронтенда к бэкенду. Все cross-origin запросы идут напрямую к бэкенду.

- timestamp: 2026-04-12T00:13:00+00:00
  checked: Деплой фронтенда и бэкенда
  found: Фронтенд на cortex-info.up.railway.app, бэкенд на cortex-production-f79a.up.railway.app — РАЗНЫЕ Railway сервисы
  implication: Браузер делает cross-origin запросы. CORS preflight (OPTIONS) ОБЯЗАТЕЛЕН перед POST-запросами.

- timestamp: 2026-04-12T00:14:00+00:00
  checked: backend/app/main.py lines 83-89
  found: CORSMiddleware настроен с allow_origins=settings.cors_origins, allow_credentials=True
  implication: CORS зависит от корректного заполнения settings.cors_origins из Railway env var

- timestamp: 2026-04-12T00:15:00+00:00
  checked: backend/app/config.py
  found: cors_origins: list[str] = ["http://localhost:3000"]
  implication: В продакшене Railway env var CORS_ORIGINS должен быть установлен и корректно распарсен pydantic-settings. Если парсинг падает, mismatch origin приводит к CORS preflight failure, что браузер показывает как неудачный запрос (выглядит как 404 во фронтенде).

- timestamp: 2026-04-12T00:16:00+00:00
  checked: railway.json
  found: Только build/deploy конфиг. Нет маршрутизации, нет конфигурации прокси.
  implication: Railway НЕ предоставляет автоматический прокси между фронтендом и бэкендом. Они полностью разделены.

- timestamp: 2026-04-12T00:17:00+00:00
  checked: конфигурация куки в auth.py lines 27-45
  found: куки устанавливаются с domain=settings.cookie_domain or None, secure=settings.cookie_secure, samesite="none" если cookie_secure иначе "lax"
  implication: Настройки куки архитектурно корректны (secure=True, samesite=none, domain=.up.railway.app). Куки будут работать, ЕСЛИ cross-origin запрос успешен.

- timestamp: 2026-04-12T00:18:00+00:00
  checked: cookie_domain config.py line 44
  found: cookie_domain: str = "" (дефолт — пустая строка)
  implication: Если Railway env var COOKIE_DOMAIN не установлен, cookie_domain="" приводит к domain=None в set_cookie, что означает куки привязаны к конкретному хосту бэкенда (cortex-production-f79a.up.railway.app). Фронтенд на cortex-info.up.railway.app НЕ получит эти куки.

root_cause: "НАЙДЕНЫ ДВЕ КОРНЕВЫЕ ПРИЧИНЫ: (1) НЕТ REVERSE PROXY между фронтендом (cortex-info.up.railway.app) и бэкендом (cortex-production-f79a.up.railway.app) — разные Railway сервисы, все auth-запросы cross-origin, требующие CORS preflight. Если CORS падает, браузер блокирует запрос, что выглядит как 404. (2) COOKIE DOMAIN по умолчанию — пустая строка — приводит к domain=None в set_cookie, привязывая куки к хосту бэкенда, невидимые для домена фронтенда."
fix: "(1) Добавлены Next.js rewrites в next.config.mjs для проксирования /api/* на бэкенд, полностью устраняя CORS. Обновлён frontend/lib/api.ts на относительные пути. (2) Добавлен валидатор parse_cors_origins в config.py для десериализации JSON-массивов из Railway env vars. (3) Изменён cookie_domain с str = '' на Optional[str] = None."
verification: "Ожидает проверки пользователем на Railway. Пользователю нужно задеплоить фронтенд и бэкенд, затем протестировать поток авторизации (регистрация, логин, установка куки)."
files_changed: ["frontend/next.config.mjs", "frontend/lib/api.ts", "backend/app/config.py"]
