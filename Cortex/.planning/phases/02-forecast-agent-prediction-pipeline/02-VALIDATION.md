---
phase: 2
slug: forecast-agent-prediction-pipeline
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-12
---

# Phase 2 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x + pytest-asyncio 1.3.0 |
| **Config file** | `backend/pyproject.toml` (already configured: `asyncio_mode = "auto"`) |
| **Quick run command** | `cd backend && python -m pytest tests/ -x -q` |
| **Full suite command** | `cd backend && python -m pytest tests/ -v --tb=short` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `cd backend && python -m pytest tests/ -x -q`
- **After every plan wave:** Run `cd backend && python -m pytest tests/ -v --tb=short`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** ~15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| T-01 | 02-01 | 1 | FC-02 | T-02-01, T-02-02 | Config loads Tavily/OpenRouter keys, available_models list | unit | `cd backend && python -c "from app.config import settings; assert hasattr(settings, 'tavily_api_key')"` | W0 | pending |
| T-02 | 02-01 | 1 | FC-02 | — | Prediction model has reasoning + confidence_score columns | unit | `cd backend && python -c "from app.models.prediction import Prediction; assert 'reasoning' in [c.key for c in Prediction.__table__.columns]"` | W0 | pending |
| T-03 | 02-01 | 1 | FC-02 | T-02-03, T-02-04 | Agent research/analyze/predict pipeline with mocked clients | unit | `cd backend && python -m pytest tests/test_agent.py -x -q` | W0 | pending |
| T-01 | 02-02 | 2 | FC-01 | T-02-06, T-02-07 | POST /forecast validates model, looks up event, stores prediction | integration | `cd backend && python -m pytest tests/test_forecast.py::TestGenerateForecast -x -q` | W0 | pending |
| T-02 | 02-02 | 2 | FC-01 | — | Forecast stored in DB, response matches | integration | `cd backend && python -m pytest tests/test_forecast.py::test_forecast_stored_in_database -x -q` | W0 | pending |
| T-01 | 02-03 | 3 | FC-03 | T-02-12 | GET /models returns config-backed model list | integration | `cd backend && python -m pytest tests/test_forecast.py::test_get_available_models_matches_config -x -q` | W0 | pending |
| T-01 | 02-03 | 3 | FC-04 | T-02-10, T-02-11 | GET /predictions returns journal ordered by created_at desc | integration | `cd backend && python -m pytest tests/test_forecast.py::test_get_event_predictions_with_data -x -q` | W0 | pending |
| T-02 | 02-03 | 3 | FC-04 | — | Journal handles empty, not-found, invalid UUID | integration | `cd backend && python -m pytest tests/test_forecast.py -k "predictions" -x -q` | W0 | pending |

*Status: pending · green · red · flaky*

---

## Wave 0 Requirements

- [ ] `backend/tests/test_agent.py` — 7 unit tests for PredictionAgent (research, analyze, predict, fallback, clamping, full pipeline)
- [ ] `backend/tests/test_forecast.py` — 11 integration tests (5 from Plan 02-02 + 6 from Plan 02-03)
- [ ] Mock fixtures for AsyncTavilyClient.search() and AsyncOpenRouter.chat.send_async() in conftest.py or test files

*Existing `backend/tests/conftest.py` already provides `client`, `db_session`, and `setup_test_db` fixtures — extend with agent mocks.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Real Tavily search returns relevant results for Polymarket events | FC-02 | Requires live API key and network | Set TAVILY_API_KEY, run agent.research() on a real event, verify results are relevant |
| OpenRouter free model returns valid JSON | FC-02 | Requires live API key and network | Set OPENROUTER_API_KEY, call agent.predict() with each free model, verify JSON parsing succeeds |
| Total forecast latency under 60 seconds | FC-01 | Timing varies by model load and network | Time a full generate_forecast() call with real API keys, verify < 60s |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references (test_agent.py, test_forecast.py, mock fixtures)
- [x] No watch-mode flags
- [x] Feedback latency < 15s

**Approval: pending**
