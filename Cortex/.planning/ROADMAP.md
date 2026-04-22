# Roadmap

Этот roadmap отражает не стартовый план, а текущее состояние после основной сборки v1-функциональности.

## Уже реализовано

### Product foundation

- Backend API на FastAPI
- Frontend на Next.js App Router
- PostgreSQL + Alembic
- JWT/cookie auth flow
- Event catalog и event details
- Forecast generation flow
- Prediction journal
- Leaderboard
- Admin dashboard
- User API keys
- Multi-provider model catalog

### Data and operations

- Ручной поиск Polymarket markets из админки
- Импорт событий в локальную БД
- Повторная синхронизация отдельного события
- Hourly resolution job для уже сохранённых событий
- DB utility endpoints в админке

## Следующий этап

### 1. Security hardening

- Зашифровать `user_api_keys.api_key`
- Проверить все auth- и admin-гварды
- Довести whitelist до обязательной политики допуска
- Пересмотреть cookie/JWT настройки под production deployment

### 2. Product clarity

- Разделить free/premium поведение моделей более явно
- Задокументировать правила выбора моделей и провайдеров
- Снизить когнитивную нагрузку в `Generate Forecast` UI

### 3. Data automation

- Решить, нужен ли автоимпорт рынков или достаточно ручной модерации
- Если нужен: проектировать безопасный sync pipeline без раздувания базы
- Добавить аудит изменений событий и импортов

### 4. Ops and repo hygiene

- Удалить build/runtime артефакты из git
- Добавить понятные runbook'и по деплою и миграциям
- Описать резервное копирование и восстановление БД
- Добавить smoke-checklist после релиза

### 5. Quality and observability

- Добавить больше автоматических тестов на forecast flow и admin flows
- Ввести нормальный audit trail для критичных действий
- Добавить централизованный logging/monitoring слой

## Не ближайший приоритет

- Mobile app
- Social/community features
- Multi-model consensus engine
- Trading automation around Polymarket
