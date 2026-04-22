---
status: fixing
trigger: "500 error on POST /api/forecast with message LLM Provider not configured"
created: "2026-04-15T00:00:00Z"
updated: "2026-04-15T00:10:00Z"
---

## Current Focus

hypothesis: Root cause confirmed and fix committed. .env.example updated. Created .env with placeholders. User must add real API keys.
test: Self-verified: config now loads non-empty values from .env. User must confirm in real environment.
expecting: User will add real keys to .env and confirm forecast works
next_action: Request human verification

## Symptoms

expected: Прогноз генерируется через OpenRouter API
actual: POST /api/forecast возвращает 500 с сообщением "LLM Provider not configured"
errors: "Failed to load resource: the server responded with a status of 500 ()" on /api/forecast
reproduction: Открыть страницу события → нажать "Generate" → 500 ошибка
started: Current problem

## Eliminated

## Evidence

- timestamp: "2026-04-15T00:05:00Z"
  checked: backend/app/routers/forecasts.py:97-99
  found: `if not settings.openrouter_api_key` guard raises HTTPException(500, "LLM Provider not configured")
  implication: This is the exact error source

- timestamp: "2026-04-15T00:06:00Z"
  checked: backend/app/config.py:53
  found: `openrouter_api_key: str = ""` with default empty string, loaded from env var OPENROUTER_API_KEY via pydantic-settings
  implication: If env var not set, defaults to empty string, triggering the guard

- timestamp: "2026-04-15T00:07:00Z"
  checked: backend/.env.example
  found: OPENROUTER_API_KEY and TAVILY_API_KEY were NOT listed in .env.example
  implication: Developer has no documentation about what env vars to set

- timestamp: "2026-04-15T00:08:00Z"
  checked: No .env file exists in backend directory
  found: ls shows only .env.example, no .env file
  implication: No local environment file to provide the API keys

- timestamp: "2026-04-15T00:09:00Z"
  checked: Direct Python import of settings
  found: openrouter_api_key='', tavily_api_key='' confirmed empty at runtime
  implication: Confirms no environment variables are set anywhere

## Resolution

root_cause: "OPENROUTER_API_KEY and TAVILY_API_KEY were not documented in .env.example, and no .env file existed. Config defaults to empty string, which triggers the guard in forecasts.py:97-99 raising 'LLM Provider not configured'."
fix: "Added OPENROUTER_API_KEY and TAVILY_API_KEY to .env.example with placeholder values. Created .env file from example. User must replace placeholders with actual API keys."
verification: "Config now loads non-empty values from .env file. Before: openrouter_api_key=''. After: openrouter_api_key='sk-or-v1-YOUR_OPENROUTER_KEY_HERE'"
files_changed: ["backend/.env.example", "backend/.env"]
