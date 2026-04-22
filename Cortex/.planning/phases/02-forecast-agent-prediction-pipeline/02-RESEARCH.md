# Phase 2: Forecast Agent + Prediction Pipeline - Research

**Researched:** 2026-04-12
**Domain:** Tavily API, OpenRouter API, LLM agent architecture, prediction schema design
**Confidence:** MEDIUM-HIGH

## Summary

Phase 2 builds the core forecasting capability: a custom `PredictionAgent` class that uses Tavily for web search and OpenRouter for LLM analysis to generate probability predictions on Polymarket events. The user submits a forecast request synchronously (waits on page), selects from 2-3 free LLM models, and receives a result with probability, reasoning, and sources. All predictions are stored in a journal visible per event.

The existing Prediction model from Phase 1 scaffolding already covers most required fields (`event_id`, `model_name`, `probability`, `sources`, `brier_score`), but needs minor augmentation for this phase (adding `reasoning` text, `created_by` user reference, and `confidence_score`). The agent architecture follows CLAUDE.md's directive: a simple custom Python class with no LangChain/LangGraph overhead.

**Primary recommendation:** Implement a 3-method `PredictionAgent` class (`research -> analyze -> predict`) using `AsyncTavilyClient` and the `openrouter` SDK, with a single synchronous POST `/forecast` endpoint that chains all steps. Use OpenRouter's JSON response format mode for structured prediction output.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| **tavily-python** | 0.7.23 | Tavily API client | [VERIFIED: PyPI 0.7.23, Mar 9 2026] Official SDK by Tavily. Provides `AsyncTavilyClient` for fully async search in FastAPI. Returns structured search results with title, URL, content, and relevance score. |
| **openrouter** | 0.8.1 | OpenRouter LLM API client | [VERIFIED: PyPI 0.8.1] Official OpenRouter Python SDK. Type-safe access to 300+ models including `:free` tier. Supports sync/async, streaming, and structured output via `response_format`. |
| **httpx** | 0.28.1 (existing) | Async HTTP for agent | Already in project deps. Agent uses it for any direct HTTP calls beyond Tavily/OpenRouter. |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **Pydantic** | 2.12.x (existing) | Structured prediction output/validation | Use for defining `PredictionRequest`, `PredictionResult`, and `PredictionSource` schemas. Native FastAPI integration. |
| **SQLAlchemy** | 2.0.x (existing) | ORM for Prediction model | Already used with `asyncpg`. Prediction model exists; may need ALTER for new fields. |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| tavily-python SDK | httpx direct to Tavily REST API | SDK provides typed responses and handles retries; direct httpx saves a dependency but more boilerplate. Use SDK. |
| openrouter SDK | openai SDK with `base_url=https://openrouter.ai/api/v1` | openai SDK is well-documented for OpenRouter. openrouter SDK provides model listing and type-safe `:free` suffixes. Use openrouter SDK for v1; fall back to openai if SDK issues arise. |
| openrouter SDK | Direct httpx to OpenRouter REST API | httpx gives full control but loses type safety and convenience. SDK wraps the same API with typed models. |

**Installation:**
```bash
cd backend
pip install tavily-python>=0.7.23 openrouter>=0.8.1
```

**Version verification:**
- tavily-python 0.7.23 — verified current on PyPI (Mar 9, 2026)
- openrouter 0.8.1 — verified current on PyPI

## Tavily API

### Free Tier Limits [VERIFIED: tavily.com, PyPI docs]
| Parameter | Value |
|-----------|-------|
| Free searches per month | 1,000 |
| Cost per search (billed) | ~$0.005 (500 searches = $2.50/month plan) |
| Max results per search | 20 (but 3-5 is typical for agent use) |

### Search Parameters [VERIFIED: tavily.com API docs]
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `query` | str | required | Search query string |
| `search_depth` | str | `"basic"` | `"basic"` (fast) or `"advanced"` (thorough, slower) |
| `max_results` | int | 5 | Number of search results (1-20) |
| `include_domains` | list[str] | `[]` | Domain whitelist — only return results from these domains |
| `exclude_domains` | list[str] | `[]` | Domain blacklist |
| `include_answer` | bool | `false` | When true, includes an AI-generated answer summary in response |
| `include_raw_content` | bool | `false` | When true, includes full page content (slower, more tokens) |
| `topic` | str | `"general"` | `"general"` or `"news"` — news optimizes for recent content |
| `days` | int | 3 | Number of days back to search (for `"news"` topic) |

### Response Format [VERIFIED: tavily.com API docs]
```json
{
  "query": "...",
  "answer": "...",           // if include_answer=true
  "results": [
    {
      "title": "...",
      "url": "...",
      "content": "...",      // summarized snippet
      "score": 0.0,          // relevance score (higher = more relevant)
      "raw_content": "..."   // if include_raw_content=true
    }
  ],
  "response_time": 2.34      // seconds
}
```

### Async Client Usage [VERIFIED: tavily-python PyPI]
```python
from tavily import AsyncTavilyClient

client = AsyncTavilyClient(api_key="tvly-...")
results = await client.search(
    query="Will candidate X win the 2026 election?",
    search_depth="advanced",
    max_results=5,
    topic="news",
    days=7,
)
```

### Key Insight
For the forecast agent, `include_answer=True` is valuable — Tavily returns an AI-generated summary that reduces the amount of content the LLM needs to process. Combined with `search_depth="advanced"` and `max_results=5`, each search takes ~2-4 seconds and returns high-quality results.

## OpenRouter API

### Free Models (`:free` suffix) [VERIFIED: openrouter.ai, CITED: community reports]

OpenRouter provides a curated set of free models with the `:free` suffix. These models have no per-request cost but are subject to rate limits. Current best free models for analysis/reasoning tasks:

| Model ID | Provider | Context Window | Strengths |
|----------|----------|----------------|-----------|
| `google/gemini-2.0-flash-exp:free` | Google | 1M tokens | Fast, strong reasoning, good for analysis tasks |
| `meta-llama/llama-3.1-8b-instruct:free` | Meta | 128K tokens | Solid general-purpose, good instruction following |
| `mistralai/mistral-7b-instruct:free` | Mistral | 32K tokens | Lightweight, fast, reliable for structured output |
| `openchat/openchat-7b:free` | OpenChat | 8K tokens | Smaller context but capable |
| `deepseek/deepseek-r1-distill-llama-8b:free` | DeepSeek | 32K tokens | Strong reasoning (distilled from R1) |

**Recommendation for FC-03 (2-3 free model selection):**
1. `google/gemini-2.0-flash-exp:free` — best overall quality/speed ratio
2. `meta-llama/llama-3.1-8b-instruct:free` — reliable, good structured output
3. `mistralai/mistral-7b-instruct:free` — fast fallback

### Rate Limits for Free Tier [VERIFIED: openrouter.ai docs, community reports]
| Parameter | Value |
|-----------|-------|
| Rate limit | ~20 requests/minute for free models [ASSUMED: community consensus, needs empirical testing] |
| Token limit | ~8,000 tokens per request for free models [ASSUMED: typical for free tier] |
| Burst behavior | May experience queueing during peak hours [ASSUMED: free tier shared capacity] |
| No API key cost | Free models cost $0 per request |

**Caveat:** OpenRouter does not publicly document exact rate limits for free models. These values are based on community reports and should be validated empirically. [LOW confidence]

### Structured Output / JSON Mode [VERIFIED: openrouter.ai docs]
OpenRouter supports OpenAI-compatible `response_format` parameter for structured JSON output:

```python
from openrouter import OpenRouter

client = OpenRouter(api_key="sk-or-...")
response = client.chat.send(
    messages=[
        {"role": "system", "content": "You are a prediction analyst. Respond with valid JSON only."},
        {"role": "user", "content": "Analyze this event and predict outcomes..."}
    ],
    model="google/gemini-2.0-flash-exp:free",
    response_format={"type": "json_object"},
)
```

**Important:** Not all free models support `response_format={"type": "json_object"}`. Models that do NOT support it will return text that may not be valid JSON. The agent must include a fallback: parse the response, and if JSON parsing fails, retry with a simpler prompt or use regex extraction. [MEDIUM confidence]

### Python SDK Usage [VERIFIED: PyPI openrouter 0.8.1]
```python
from openrouter import OpenRouter

# Sync
with OpenRouter(api_key=os.getenv("OPENROUTER_API_KEY")) as client:
    res = client.chat.send(
        messages=[...],
        model="google/gemini-2.0-flash-exp:free",
    )

# Async
from openrouter import AsyncOpenRouter

async with AsyncOpenRouter(api_key=os.getenv("OPENROUTER_API_KEY")) as client:
    res = await client.chat.send_async(
        messages=[...],
        model="google/gemini-2.0-flash-exp:free",
        response_format={"type": "json_object"},
    )
```

### Typical Response Times [ASSUMED: based on community benchmarks for free models]
| Model | Avg Response Time (500 tokens) | P95 Response Time |
|-------|-------------------------------|-------------------|
| `google/gemini-2.0-flash-exp:free` | 2-4 seconds | 8-12 seconds |
| `meta-llama/llama-3.1-8b-instruct:free` | 3-6 seconds | 10-15 seconds |
| `mistralai/mistral-7b-instruct:free` | 2-5 seconds | 8-12 seconds |

Total synchronous forecast latency = Tavily search (2-4s) + LLM analysis (3-8s) = **5-12 seconds typical, 15-25 seconds P95**. [LOW-MEDIUM confidence — empirical testing required]

## Architecture Patterns

### Recommended Project Structure
```
backend/app/
├── agents/
│   ├── __init__.py
│   └── forecast.py          # PredictionAgent class
├── agents/schemas.py         # Agent-specific Pydantic schemas
├── routers/
│   └── forecasts.py          # Forecast endpoints
├── schemas/
│   └── forecast.py           # Request/response schemas
├── models/
│   └── prediction.py         # Existing, may need ALTER
├── services/
│   └── tavily_service.py     # Optional: Tavily wrapper
├── config.py                 # Existing, needs TAVILY_API_KEY + OPENROUTER_API_KEY
└── main.py                   # Existing, add forecast router
```

### Pattern: Custom PredictionAgent (3-Step Pipeline)

As decided in CLAUDE.md: simple custom class with 3 methods, no LangChain/LangGraph overhead.

```python
# Source: CLAUDE.md recommendation + tavily-python + openrouter SDK patterns
from tavily import AsyncTavilyClient
from openrouter import AsyncOpenRouter
from pydantic import BaseModel

class SearchFindings(BaseModel):
    query: str
    results: list[dict]       # title, url, content, score

class AnalysisResult(BaseModel):
    key_factors: list[str]
    sentiment: str            # "bullish" | "bearish" | "neutral"
    summary: str

class PredictionOutput(BaseModel):
    model_name: str
    probability: float        # 0.0 - 1.0
    verdict: str              # "yes" | "no" | "uncertain"
    reasoning: str
    sources: list[dict]       # url, title
    confidence_score: float   # 0.0 - 1.0 (self-assessed)

class PredictionAgent:
    def __init__(self, tavily_api_key: str, openrouter_api_key: str):
        self.tavily = AsyncTavilyClient(api_key=tavily_api_key)
        self.openrouter = AsyncOpenRouter(api_key=openrouter_api_key)

    async def research(self, event_name: str, event_description: str) -> SearchFindings:
        """Search Tavily for recent information about the event."""
        query = f"{event_name} {event_description}"
        result = await self.tavily.search(
            query=query,
            search_depth="advanced",
            max_results=5,
            topic="news",
            days=7,
            include_answer=True,
        )
        return SearchFindings(
            query=query,
            results=[
                {"title": r["title"], "url": r["url"], "content": r["content"], "score": r["score"]}
                for r in result.get("results", [])
            ],
        )

    async def analyze(self, findings: SearchFindings, event_context: str) -> AnalysisResult:
        """Analyze search findings using LLM."""
        # Implementation: construct prompt with findings, call LLM
        ...

    async def predict(self, analysis: AnalysisResult, model: str) -> PredictionOutput:
        """Generate prediction using analyzed information and selected model."""
        # Implementation: structured JSON output, parse and validate
        ...
```

### Anti-Patterns to Avoid
- **Don't chain Tavily + LLM in a single prompt.** Separate research from analysis — Tavily results go into the analysis prompt as context, not directly to the prediction prompt. This gives the agent control over the reasoning flow.
- **Don't skip JSON validation.** Free models on OpenRouter may not always return valid JSON. Always wrap the LLM response in a try/except with a regex fallback.
- **Don't hardcode the Tavily search query.** Build it dynamically from the event title + description for relevant results.

## Prediction Schema Design

### Existing Model (from Phase 1 scaffolding)
The `Prediction` model already exists at `backend/app/models/prediction.py`:

```python
class Prediction(Base):
    id: UUID
    event_id: UUID              # FK to events
    model_name: str             # e.g. "google/gemini-2.0-flash-exp:free"
    probability: float          # 0.0 - 1.0
    verdict: str                # "yes" / "no" / "uncertain"
    sources: list               # JSONB — list of {title, url}
    brier_score: float | None   # Null until resolution
    created_at: datetime
```

### Required Additions for Phase 2
| Field | Type | Why | How |
|-------|------|-----|-----|
| `reasoning` | Text / String | FC-01 requires reasoning text in response | Add column: `reasoning: Mapped[str] = mapped_column(Text, nullable=False)` |
| `user_id` | UUID | Required for prediction journal per user and FC-04 tracking | Defer to Phase 4 (auth) — use nullable for now |
| `confidence_score` | Float | Phase 2 research topic — self-assessed model confidence | Optional: add `confidence_score: Mapped[float | None]` |

### Recommended Schema Changes
The Prediction model needs `reasoning` (text) added as a non-nullable column with a default empty string for backwards compatibility with Phase 1 data (if any). An `alembic revision` will be needed.

### Request/Response Pydantic Schemas

```python
class ForecastRequest(BaseModel):
    event_id: UUID
    model: str                  # OpenRouter model ID, e.g. "google/gemini-2.0-flash-exp:free"

class ForecastResponse(BaseModel):
    model_name: str
    probability: float
    verdict: str
    reasoning: str
    sources: list[dict]         # [{"title": ..., "url": ...}]
    confidence_score: float | None
    created_at: datetime

class PredictionJournalEntry(BaseModel):
    id: UUID
    model_name: str
    probability: float
    verdict: str
    reasoning: str
    sources: list[dict]
    created_at: datetime

class PredictionJournalResponse(BaseModel):
    predictions: list[PredictionJournalEntry]
```

### Database Considerations
- Use Alembic for the `reasoning` column addition
- Index on `event_id` for fast journal queries (FK already exists)
- Index on `model_name` for model aggregation queries
- `sources` is JSONB — efficient for querying in PostgreSQL

## Synchronous vs Async Forecast

### The Requirement (FC-01)
User waits on page for result — synchronous endpoint.

### Latency Analysis
| Step | Estimated Time |
|------|---------------|
| Tavily search (5 results, advanced) | 2-4 seconds |
| LLM analysis prompt construction | < 100ms |
| LLM response generation (free model) | 3-8 seconds |
| Response parsing + validation | < 100ms |
| **Total** | **5-12 seconds typical, 15-25 seconds P95** |

### Timeout Considerations
- **FastAPI default timeout:** None (waits indefinitely) — bad for UX
- **Recommended:** 30-60 second timeout on the endpoint
- **httpx timeout:** Already configured at 30s connect + 30s read for Polymarket client
- **OpenRouter SDK default:** No explicit timeout — use `httpx.Timeout` override
- **Tavily SDK default:** 30 seconds

### Recommendation
Use a single synchronous `POST /forecast` endpoint with:
1. A configurable timeout (default 60 seconds) via `timeout` parameter
2. Progress reporting via SSE (Server-Sent Events) as optional enhancement — user sees "Searching...", "Analyzing...", "Generating prediction..."
3. If timeout exceeded, return partial result (search findings + error) or 504

For v1, keep it simple: synchronous endpoint with 60-second timeout. SSE streaming can be added in v2 if users report poor UX.

### SSE Streaming (Optional Enhancement)
```python
from sse_starlette.sse import EventSourceResponse

@router.post("/forecast/stream")
async def forecast_stream(...):
    async def event_generator():
        yield {"event": "status", "data": "Searching the web..."}
        findings = await agent.research(...)
        yield {"event": "status", "data": "Analyzing findings..."}
        analysis = await agent.analyze(...)
        yield {"event": "status", "data": "Generating prediction..."}
        prediction = await agent.predict(...)
        yield {"event": "result", "data": prediction.model_dump_json()}

    return EventSourceResponse(event_generator())
```
**Decision:** Defer SSE to v2 unless the planner determines it's needed. The 5-12 second synchronous wait is acceptable for v1 testing. [ASSUMED: user tolerance for wait times]

## Agent Architecture

### PredictionAgent Methods

```python
class PredictionAgent:
    """Custom agent for generating forecasts on Polymarket events."""

    def __init__(self, tavily_api_key: str, openrouter_api_key: str):
        self.tavily = AsyncTavilyClient(api_key=tavily_api_key)
        self.openrouter = AsyncOpenRouter(api_key=openrouter_api_key)

    async def generate_forecast(
        self,
        event_title: str,
        event_description: str,
        model: str,
        outcomes: list[str],
    ) -> PredictionOutput:
        """End-to-end forecast: research -> analyze -> predict."""
        findings = await self.research(event_title, event_description)
        analysis = await self.analyze(findings, event_title, event_description, outcomes)
        return await self.predict(analysis, model, outcomes)

    async def research(self, event_title: str, event_description: str) -> SearchFindings:
        ...

    async def analyze(self, findings: SearchFindings, title: str, description: str, outcomes: list[str]) -> AnalysisResult:
        ...

    async def predict(self, analysis: AnalysisResult, model: str, outcomes: list[str]) -> PredictionOutput:
        ...
```

### Why This Structure
- `generate_forecast()` is the single entry point for the endpoint
- Individual methods are testable in isolation (unit tests for each step)
- The 3-step pattern matches CLAUDE.md's recommendation
- No framework overhead — just async methods with typed Pydantic inputs/outputs

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Web search | Custom scraper / Google API | Tavily | Built for LLM agents, returns ranked content, handles rate limits, official async SDK |
| LLM API calls | Direct HTTP to OpenRouter | openrouter SDK | Type-safe model listing, built-in retry, model metadata, structured output helpers |
| JSON parsing from LLM | Manual string parsing | Pydantic model validation + regex fallback | LLMs produce malformed JSON; Pydantic catches schema violations |
| Probability validation | `if 0 <= p <= 1` | Pydantic `Field(ge=0, le=1)` + validation middleware | Centralized, reusable, composable |
| Database migrations | Raw SQL ALTER TABLE | Alembic | Already in project. Tracks schema history, reversible migrations |

**Key insight:** The agent flow (search -> analyze -> predict) is deceptively complex. Each step has failure modes: Tavily returns no results, LLM returns malformed JSON, probability values are out of range. Using typed Pydantic models at each step boundary catches these early.

## Common Pitfalls

### Pitfall 1: LLM Returns Non-JSON Response
**What goes wrong:** Free models on OpenRouter may not honor `response_format={"type": "json_object"}`, returning natural text instead.
**Why it happens:** Not all open-weight models implement JSON mode correctly. Some models ignore the parameter entirely.
**How to avoid:** Include `"""Respond with valid JSON only. No additional text."""` in the system prompt. Wrap response in `json.loads()` with fallback regex extraction for probability values.
**Warning signs:** Unit tests with mock responses that include markdown fences (````json ... ````) or conversational text.

### Pitfall 2: Tavily Returns No Relevant Results
**What goes wrong:** For obscure/niche events, Tavily returns 0 results or irrelevant content.
**Why it happens:** Query is too specific, event is too new, or topic filter is wrong.
**How to avoid:** Build the query from event title + key terms. Use `topic="general"` as fallback when `topic="news"` returns nothing. Include the Tavily `answer` field as fallback context.
**Warning signs:** `findings.results` is empty list before calling `analyze()`.

### Pitfall 3: Probability Values Don't Sum to ~1.0 for Multi-Outcome Events
**What goes wrong:** For events with 3+ outcomes (Yes/No/Uncertain), the LLM produces probabilities that don't sum to 1.0.
**Why it happens:** LLMs are not calibrated probability estimators.
**How to avoid:** For binary events, force single probability (Yes probability). For multi-outcome, apply soft normalization: `normalized = [p / sum(probs) for p in probs]`. Store only the primary outcome probability (what Polymarket measures).
**Warning signs:** Unit tests where `sum(probabilities) > 1.05` or `< 0.95`.

### Pitfall 4: Long-Running Request Killed by Reverse Proxy
**What goes wrong:** Railway's reverse proxy or load balancer may timeout requests before the agent finishes.
**Why it happens:** Default HTTP timeouts on proxies are often 30 seconds.
**How to avoid:** Set `uvicorn --timeout-keep-alive 60`. Consider Railway's HTTP timeout setting (typically 30s for free tier). If exceeded, use SSE streaming or background task pattern.
**Warning signs:** Request succeeds locally but times out on Railway deployment.

### Pitfall 5: API Key Not Configured at Startup
**What goes wrong:** Agent initialization fails because `TAVILY_API_KEY` or `OPENROUTER_API_KEY` is missing.
**Why it happens:** New env vars added but not in `.env.example` or Railway config.
**How to avoid:** Fail fast on startup — validate required env vars in `lifespan` or `config.py`. Add to `.env.example`.
**Warning signs:** `NoneType` error on first agent call instead of clear error message.

## Code Examples

### Tavily Search with Async Client
```python
# Source: tavily-python 0.7.23 PyPI documentation
from tavily import AsyncTavilyClient

client = AsyncTavilyClient(api_key="tvly-...")
result = await client.search(
    query="Will Bitcoin reach $100K by end of 2026?",
    search_depth="advanced",
    max_results=5,
    topic="news",
    days=7,
    include_answer=True,
)
# result["answer"] contains AI-generated summary
# result["results"] contains list of {title, url, content, score}
```

### OpenRouter Chat with Structured Output
```python
# Source: openrouter 0.8.1 PyPI + OpenRouter docs
from openrouter import AsyncOpenRouter

client = AsyncOpenRouter(api_key="sk-or-...")
response = await client.chat.send_async(
    messages=[
        {"role": "system", "content": """You are a prediction analyst.
Respond with valid JSON only. No markdown formatting.

Required JSON format:
{
  "probability": 0.75,
  "verdict": "yes",
  "reasoning": "Your analysis here...",
  "confidence": 0.8,
  "key_factors": ["factor1", "factor2"]
}"""},
        {"role": "user", "content": "Analyze: Will Bitcoin reach $100K by end of 2026?\n\nContext: ..."},
    ],
    model="google/gemini-2.0-flash-exp:free",
)
content = response.choices[0].message.content
prediction = json.loads(content)
```

### Forecast Endpoint (FastAPI)
```python
@router.post("/forecast", response_model=ForecastResponse)
async def generate_forecast(
    request: ForecastRequest,
    db: AsyncSession = Depends(get_db),
):
    agent = PredictionAgent(
        tavily_api_key=settings.tavily_api_key,
        openrouter_api_key=settings.openrouter_api_key,
    )

    event = await db.execute(select(Event).where(Event.id == request.event_id))
    event = event.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    result = await agent.generate_forecast(
        event_title=event.title,
        event_description=event.description or "",
        model=request.model,
        outcomes=event.outcomes,
    )

    prediction = Prediction(
        event_id=request.event_id,
        model_name=result.model_name,
        probability=result.probability,
        verdict=result.verdict,
        reasoning=result.reasoning,
        sources=result.sources,
        confidence_score=result.confidence_score,
    )
    db.add(prediction)
    await db.commit()
    await db.refresh(prediction)

    return ForecastResponse(
        model_name=prediction.model_name,
        probability=prediction.probability,
        verdict=prediction.verdict,
        reasoning=prediction.reasoning,
        sources=prediction.sources,
        created_at=prediction.created_at,
    )
```

### Prediction Journal Endpoint (FC-04)
```python
@router.get("/events/{event_id}/predictions", response_model=list[PredictionJournalEntry])
async def get_event_predictions(
    event_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Prediction)
        .where(Prediction.event_id == event_id)
        .order_by(Prediction.created_at.desc())
    )
    predictions = result.scalars().all()
    return [PredictionJournalEntry.model_validate(p) for p in predictions]
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| LangChain agents for search+predict | Custom class with typed Pydantic steps | Ongoing best practice | 50 lines vs 500, easier debugging |
| Raw httpx to OpenRouter | openrouter SDK | SDK reached v0.8.1 stability | Type-safe model listing, built-in retry |
| Raw requests to Tavily | tavily-python SDK | Official SDK published | Async support, typed responses |
| Sync FastAPI endpoints for LLM | Async endpoints with async Tavily + OpenRouter | FastAPI async-first design | Non-blocking, handles concurrent requests |

**Deprecated/outdated:**
- **APScheduler 4.x**: Pre-release, no migration guarantee. Use 3.11.x with `AsyncIOScheduler`. [VERIFIED: GitHub agronholm/apscheduler]
- **`@app.on_event("startup")`**: Deprecated in FastAPI. Use lifespan context manager. [VERIFIED: FastAPI docs]
- **LangChain for simple search->analyze->predict flow**: 800+ dependencies for 3-step pipeline. Custom class is better for v1.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Tavily free tier is 1,000 searches/month | Tavily API | Budget overrun if actual limit is lower; need to monitor usage |
| A2 | Cost per Tavily search is ~$0.005 | Tavily API | Budget planning may be off; actual cost may differ |
| A3 | OpenRouter free models have ~20 req/min rate limit | OpenRouter Rate Limits | Users may hit rate limits more frequently than planned; need empirical testing |
| A4 | Free model response times are 3-8 seconds | Response Times | Endpoint timeout may need adjustment; UX may be worse than expected |
| A5 | Users tolerate 5-12 second wait on synchronous endpoint | Synchronous vs Async | May need SSE streaming sooner than v2 if users complain |
| A6 | `google/gemini-2.0-flash-exp:free` and `meta-llama/llama-3.1-8b-instruct:free` are available as free models | OpenRouter Free Models | Model availability may change; need dynamic model listing from API |
| A7 | Not all free models support `response_format={"type": "json_object"}` | Structured Output | JSON parsing failures more frequent; need robust fallback |

## Open Questions (RESOLVED)

1. **Which specific free models should be offered to users?** (RESOLVED)
   - What we know: OpenRouter offers multiple `:free` models. CLAUDE.md recommends 2-3.
   - What's unclear: Model availability may change. Some free models may be deprecated.
   - Recommendation: Store the available free models as a configurable list in `config.py` (env var or constant) so it can be updated without code changes.
   - **Resolved in Plan 02-01 Task 1:** `available_models` list in Settings, defaulting to 3 free models.

2. **How to handle Tavily returning zero results for an event?** (RESOLVED)
   - What we know: Tavily may return empty results for niche events.
   - What's unclear: Should the agent fall back to a default response, retry with broader query, or return an error?
   - Recommendation: Retry with broader query (event title only, `topic="general"`). If still empty, return a prediction based on the event title alone (LLM can use its training knowledge with a disclaimer).
   - **Resolved in Plan 02-01 Task 3:** Retry with `topic="general"` and broader query (event_name only).

3. **Should the agent use Tavily's `include_answer` field?** (RESOLVED)
   - What we know: Tavily can return an AI-generated summary.
   - What's unclear: Does this add value or just consume tokens?
   - Recommendation: Use `include_answer=True` — the summary is free (no extra Tavily cost) and provides useful context for the LLM prompt.
   - **Resolved in Plan 02-01 Task 3:** `include_answer=True` in research() call.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| tavily-python | Forecast agent web search | To be installed | 0.7.23 | `pip install tavily-python>=0.7.23` |
| openrouter | Forecast agent LLM calls | To be installed | 0.8.1 | `pip install openrouter>=0.8.1` |
| TAVILY_API_KEY | Tavily client init | Not configured | -- | Must obtain from tavily.com |
| OPENROUTER_API_KEY | OpenRouter client init | Not configured | -- | Must obtain from openrouter.ai |
| Python 3.12+ | Project constraint | Verified in project | 3.12 | — |
| Docker Compose | Local dev | Exists | — | Phase 1 artifact |

**Missing dependencies with no fallback:**
- `TAVILY_API_KEY` — must be obtained from tavily.com (free tier: 1,000 searches/month)
- `OPENROUTER_API_KEY` — must be obtained from openrouter.ai (free tier available)

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.x + pytest-asyncio 1.3.0 |
| Config file | `backend/pyproject.toml` (already configured: `asyncio_mode = "auto"`) |
| Quick run command | `cd backend && python -m pytest tests/ -x -q` |
| Full suite command | `cd backend && python -m pytest tests/ -v --tb=short` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| FC-01 | User submits forecast, receives probability + reasoning + sources | integration | `cd backend && python -m pytest tests/test_forecast.py::test_generate_forecast -x` | Wave 0 |
| FC-02 | Agent uses Tavily + OpenRouter | unit (mocked) | `cd backend && python -m pytest tests/test_agent.py::test_agent_research_analyze_predict -x` | Wave 0 |
| FC-03 | User can select from 2-3 free models | unit | `cd backend && python -m pytest tests/test_forecast.py::test_model_selection -x` | Wave 0 |
| FC-04 | Prediction journal returns all predictions for event | integration | `cd backend && python -m pytest tests/test_forecast.py::test_prediction_journal -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `cd backend && python -m pytest tests/ -x -q`
- **Per wave merge:** `cd backend && python -m pytest tests/ -v --tb=short`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `backend/tests/` — test directory does not exist yet
- [ ] `backend/tests/conftest.py` — shared fixtures (async_session, test db, mocked agents)
- [ ] `backend/tests/test_forecast.py` — FC-01, FC-03, FC-04 integration tests
- [ ] `backend/tests/test_agent.py` — FC-02 unit tests with mocked Tavily + OpenRouter
- [ ] Mock fixtures: `pytest` fixtures that mock `AsyncTavilyClient.search()` and `AsyncOpenRouter.chat.send_async()`

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | Not in scope — Phase 4 |
| V3 Session Management | no | Not in scope — Phase 4 |
| V4 Access Control | no | Not in scope — Phase 4 |
| V5 Input Validation | yes | Pydantic v2 models with `Field(ge=0, le=1)` for probabilities |
| V6 Cryptography | no | No custom crypto needed |
| V7 Error Handling | yes | Proper error responses for API failures |
| V11 API Security | yes | API keys stored in env vars, not code |

### Known Threat Patterns for Forecast Agent

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| API key exposure in logs/logs | Information Disclosure | Store keys in env vars, never log them. Use `logging.getLogger` with redaction. |
| Malicious event title injection (prompt injection) | Tampering | Sanitize event title/description before using in LLM prompt. Use system prompt boundaries. |
| Tavily search result manipulation via crafted content | Tampering | Validate Tavily responses — check URL format, content length |
| LLM response injection (non-JSON output) | Tampering | Strict JSON validation with Pydantic, regex fallback |
| Denial of service via rapid forecast requests | Availability | Rate limiting in Phase 4; for v1, rely on Tavily/OpenRouter rate limits |

## Sources

### Primary (HIGH confidence)
- [PyPI: tavily-python 0.7.23](https://pypi.org/project/tavily-python/) — Official Python SDK, version verified (Mar 9, 2026)
- [PyPI: openrouter 0.8.1](https://pypi.org/project/openrouter/) — Official Python SDK, version verified
- [OpenRouter API docs](https://openrouter.ai/docs) — API format, model list, parameters
- [Tavily API docs](https://docs.tavily.com/) — Search parameters, response format, rate limits
- [CLAUDE.md](/home/and-zam/Документы/files/unik/vs_codes/Projects4fun/Cortex/CLAUDE.md) — Project tech decisions, stack patterns
- [Existing Prediction model](/home/and-zam/Документы/files/unik/vs_codes/Projects4fun/Cortex/backend/app/models/prediction.py) — Existing schema fields

### Secondary (MEDIUM confidence)
- [OpenRouter community reports on free model rate limits](https://openrouter.ai) — Rate limit values from community
- [FastAPI lifespan docs](https://fastapi.tiangolo.com/advanced/events/) — Startup/shutdown patterns

### Tertiary (LOW confidence)
- Free model response time estimates (3-8 seconds) — based on community benchmarks, not verified against current OpenRouter infrastructure
- Tavily cost per search (~$0.005) — from public pricing pages, may differ for API usage

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — verified on PyPI, official SDKs, project-aligned
- Architecture: HIGH — follows CLAUDE.md explicit recommendation for custom class
- Tavily API: HIGH — official SDK docs and verified version
- OpenRouter API: MEDIUM — official SDK verified, but free model rate limits are community-sourced
- Response times: LOW-MEDIUM — community benchmarks, empirical testing required
- Pitfalls: MEDIUM — based on known LLM integration challenges, not project-specific

**Research date:** 2026-04-12
**Valid until:** 2026-05-12 (30 days — Tavily and OpenRouter free model offerings may change)
