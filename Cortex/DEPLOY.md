# Руководство по деплою на Railway

## Структура проекта

```
Cortex/
├── backend/          # FastAPI (Dockerfile)
├── frontend/         # Next.js 14 (Dockerfile)
├── railway.json      # Конфиг Railway
└── docker-compose.yml  # Локальная разработка
```

## Шаги настройки

### 1. Создание проекта на Railway

1. Перейдите на https://railway.app и войдите
2. Нажмите "New Project" → "Deploy from GitHub repo"
3. Подключите ваш репозиторий Cortex

### 2. Добавление PostgreSQL

1. В проекте Railway нажмите "New" → "Database" → "Add PostgreSQL"
2. Railway создаст управляемый экземпляр PostgreSQL
3. Скопируйте `DATABASE_URL` из переменных сервиса PostgreSQL

### 3. Деплой Backend

1. Нажмите "New" → "GitHub Repo" → выберите репозиторий Cortex
2. Railway автоматически обнаружит `backend/Dockerfile`
3. Установите **Root Directory** в `backend`
4. Добавьте переменные окружения:

| Переменная | Значение | Примечание |
|----------|-------|-------|
| `DATABASE_URL` | `postgresql+asyncpg://...` | Из сервиса PostgreSQL |
| `JWT_SECRET` | `<случайная-строка>` | Сгенерировать через `openssl rand -hex 32` |
| `CORS_ORIGINS` | `["https://your-frontend.railway.app"]` | URL вашего фронтенда |
| `TAVILY_API_KEY` | `tvly-...` | Ваш Tavily API ключ |
| `OPENROUTER_API_KEY` | `sk-or-...` | Ваш OpenRouter API ключ |
| `COOKIE_SECURE` | `true` | Только HTTPS |
| `COOKIE_DOMAIN` | не задавать | Удалите — браузер отклоняет wildcard-домены |

5. Деплой — Railway соберёт и запустит backend

### 4. Деплой Frontend

1. Нажмите "New" → "GitHub Repo" → выберите репозиторий Cortex
2. Установите **Root Directory** в `frontend`
3. Добавьте переменные окружения:

| Переменная | Значение | Примечание |
|----------|-------|-------|
| `BACKEND_URL` | `https://your-backend.railway.app` | URL вашего бекенда |

4. Деплой — Railway соберёт и запустит фронтенд

### 5. Проверка деплоя

1. Откройте URL фронтенда
2. Зарегистрируйте новый аккаунт
3. Войдите и проверьте, что авторизация работает
4. Просмотрите события и запросите прогноз
5. Откройте страницу таблицы лидеров

## Настройка cookies

Для авторизации через API-прокси (фронтенд проксирует `/api/*` к бекенду):

- `COOKIE_SECURE=true` — требуется для HTTPS
- `COOKIE_DOMAIN` — **не задавать**. Браузеры отклоняют wildcard-домены вроде `.railway.app`. Без этого параметра cookie привязываются к конкретному домену бекенда, а API-прокси на фронтенде передаёт их как same-origin.

## Миграции базы данных

Alembic миграции запускаются автоматически при старте контейнера бекенда через Dockerfile:
```dockerfile
RUN alembic upgrade head
```

Если миграции не прошли, бекенд всё равно запустится и повторит при следующем деплое.

## Локальное тестирование перед деплоем

```bash
# Запуск локальных сервисов
docker compose up -d

# Запуск миграций
cd backend && alembic upgrade head

# Тест бекенда
curl http://localhost:8000/health

# Тест фронтенда
cd ../frontend && npm run dev
```

## Устранение проблем

### Cookies не работают в продакшене
- Убедитесь, что `COOKIE_SECURE=true` и `COOKIE_DOMAIN` **не задан**
- API-прокси на фронтенде (`app/api/[[...path]]/route.ts`) передаёт запросы к бекенду как same-origin
- Проверьте инструменты разработчика → Application → Cookies

### Ошибки CORS
- Добавьте URL фронтенда в `CORS_ORIGINS` в переменных бекенда
- Формат: `["https://frontend-url.railway.app"]`

### Не удаётся подключение к базе данных
- Убедитесь, что `DATABASE_URL` указывает на сервис Railway PostgreSQL
- Используйте внутренний Railway URL (не публичный)

### Сборка не проходит
- Проверьте, что пути в Dockerfile соответствуют структуре репозитория
- Убедитесь, что `pyproject.toml` и `package.json` находятся в своих директориях
