---
status: investigating
trigger: "Пользователь не может авторизоваться — аккаунт есть в БД, но после логина редиректит на страницу евентов и в консоли ошибка 401 на GET /api/auth/me"
created: 2026-04-13T00:00:00Z
updated: 2026-04-13T00:00:00Z
---

## Текущий фокус
hypothesis: Запросы авторизации (login, me) идут напрямую к бэкенду через cross-origin. Login устанавливает куки, но куки могут не отправляться обратно с /api/auth/me из-за одного из: (a) несовпадение домена куки, (b) некорректная настройка CORS/credentials, (c) Next.js middleware перехватывает auth-пути. Нужно проверить точный механизм.
test: Отслеживание полного потока авторизации: login → установка куки → /api/auth/me → чтение куки
expecting: Найти точку, где куки теряются или не отправляются обратно
next_action: Проверить наличие environment-specific проблем и протестировать поток авторизации

## Симптомы

expected: После логина пользователь должен быть аутентифицирован, и /api/auth/me должен возвращать данные пользователя
actual: После логина — редирект на страницу событий, затем GET /api/auth/me возвращает 401
errors: "api/auth/me:1 Failed to load resource: the server responded with a status of 401 ()"
reproduction: Войти в существующий аккаунт → редирект на события → 401 на /api/auth/me
started: Текущая проблема в продакшене, после того как предыдущий фикс auth-404 был задеплоен

## Исключено

- Логика авторизации на бэкенде корректна (login создаёт токены, правильно устанавливает куки)
- Зависимость `get_current_user` корректна (читает куки, декодирует JWT, ищет пользователя)
- `cookie_domain` равен `None` (корректно для proxy-подхода)
- `cookie_secure` равен `True` (корректно для HTTPS продакшена)
- CORS middleware настроен с `allow_credentials=True`
- Первый фикс (удаление AUTH_PATHS cross-origin маршрутизации) НЕ решил проблему — куки всё ещё пусты после логина
- Второй фикс (rewrites в next.config.mjs) — BACKEND_URL пустой в layout.tsx (`window.__ENV__={BACKEND_URL:""}`), rewrites могут не работать

## Попытки

### Попытка 1 (НЕУДАЧА): Удалить AUTH_PATHS cross-origin маршрутизацию
1. `frontend/lib/api.ts` имел `AUTH_PATHS`, который направлял auth-запросы ПРЯМО на бэкенд cross-origin через `getApiUrl()`
2. Удалён AUTH_PATHS, все запросы теперь используют относительные пути через middleware proxy
3. Результат: Куки всё ещё пусты после логина — фикс не сработал

### Попытка 2 (НЕУДАЧА): Заменить Edge middleware на Next.js rewrites
1. `frontend/middleware.ts` проксирует ВСЕ `/api/*` на бэкенд через Edge Runtime `fetch()`
2. Удалён middleware.ts, добавлены rewrites в next.config.mjs
3. **Ключевое обнаружение:** RSC ответ показывает `window.__ENV__={BACKEND_URL:""};` — BACKEND_URL пуст на уровне сервера
4. Rewrites с пустым BACKEND_URL destination = `/api/:path*` (тот же путь) — Next.js обнаруживает это и не делает rewrite
5. Результат: Запросы /api/* идут к самому Next.js (нет обработчика) — должны быть 404, но события всё равно загружаются (кеш?)

### Попытка 3 (В ПРОЦЕССЕ): Создать обработчик API route
1. Создан `frontend/app/api/[[...path]]/route.ts` — catch-all обработчик маршрута, проксирующий /api/* на бэкенд
2. Route handler работает в Node.js runtime (не Edge) — более надёжно для пересылки Set-Cookie
3. Удалены rewrites из next.config.mjs — не нужны при наличии API route
4. **Ключевая проблема:** Если BACKEND_URL действительно пустой, API route вернёт 502. Нужно проверить, что env var установлен.

## Решение
root_cause:
fix:
verification:
files_changed: ["frontend/app/api/[[...path]]/route.ts", "frontend/next.config.mjs"]

## Дополнительные находки

### Страница профиля
**Существует:** `frontend/app/profile/page.tsx` — Показывает email, план, дата регистрации, статус, кнопка выхода. Защищён через `ProtectedRoute`.

### Панель администратора
**Backend API существует:** `backend/app/routers/admin.py` — Эндпоинты для списка пользователей, вайтлистинга, отклонения, продвижения. Все требуют `get_admin_user`.
**Frontend UI: ОТСУТСТВУЕТ** — Нет маршрута `/admin` во фронтенде. Функционал админки доступен только через API.

## Уровень уверенности
**Средний (50%)** — Подход с API route должен сработать, если env var BACKEND_URL правильно установлен в Railway для сервиса фронтенда.
