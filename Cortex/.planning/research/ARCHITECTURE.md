# Architecture Research Snapshot

## Runtime architecture

```text
Next.js frontend
  -> server-side proxy route
FastAPI backend
  -> auth router
  -> events router
  -> forecast router
  -> admin router
  -> user API keys router
  -> APScheduler resolution job
  -> PostgreSQL
```

## Backend composition

### API surface

- `auth` — регистрация, логин, refresh, logout, current user
- `events` — список событий, категории, event details
- `forecast` — каталог моделей, predictions list, forecast stream, leaderboard
- `admin` — users, models, Polymarket search/import/resync/delete, db tools
- `user` — пользовательские API-ключи

### Domain services

- Forecast orchestration: собирает event context, search context и вызов провайдера
- Provider/model resolution: определяет доступные модели и валидирует выбранного провайдера
- Resolution service: проверяет resolved markets и обновляет скоринг
- Quota service: ограничивает бесплатный дневной usage

## Frontend composition

- Public marketing + app shell
- Event list screen
- Event detail screen with `Generate Forecast`
- Profile screen with BYOK management
- Admin dashboard with event management, including calendar mode for deadlines

## Architecture decisions reflected in code

- Backend и frontend разделены, но frontend использует proxy route для same-origin доступа к API
- События хранятся локально в БД, а не читаются напрямую из Polymarket на каждом экране
- Генерация прогноза зависит от user-owned provider credentials
- Scheduler не импортирует весь рынок, а обслуживает lifecycle уже сохранённых событий

## Constraints to remember

- Встроенный scheduler предполагает аккуратный deployment без неконтролируемого дублирования воркеров
- Текущая архитектура удобно поддерживает curated catalog событий, но не giant-scale ingestion pipeline
- User API keys сейчас представляют собой чувствительный слой, который требует отдельного security hardening
