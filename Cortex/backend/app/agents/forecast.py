import asyncio
import json
import logging
import re

from openrouter.errors import TooManyRequestsResponseError
from tavily import AsyncTavilyClient

from app.agents.providers import LLMProvider, create_providers
from app.agents.schemas import AnalysisResult, PredictionOutput, SearchFindings

logger = logging.getLogger("cortex.agent")

# OpenRouter free models share an account-wide per-minute rate limit.
# After exhausting all models, wait for the window to reset.
_MAX_RETRIES = 2
_RETRY_DELAY = 65  # seconds — wait for per-minute window to reset


def _parse_model_id(model_id: str) -> tuple[str, str]:
    """Split 'provider:actual_model' into (provider, actual_model)."""
    if ":" in model_id:
        parts = model_id.split(":", 1)
        return parts[0], parts[1]
    return "openrouter", model_id


def _short_name(model_id: str) -> str:
    """Human-readable short name for logging."""
    provider, actual = _parse_model_id(model_id)
    return actual.split("/")[-1].replace(":free", "")


class PredictionAgent:
    """Custom agent for generating forecasts on Polymarket events.

    Pipeline: research (Tavily) -> analyze (LLM) -> predict (LLM structured output)
    Supports multi-provider fallback across all configured LLM providers.
    """

    DEFAULT_MODEL = "openrouter:google/gemma-4-31b-it:free"

    def __init__(self, tavily_api_key: str, providers: dict[str, LLMProvider]):
        self.tavily = AsyncTavilyClient(api_key=tavily_api_key)
        self.providers = providers

    async def _call_with_retry(
        self,
        messages: list[dict],
        model: str,
        auto_fallback: bool = False,
        available_models: list[str] | None = None,
        log_cb=None,
        **kwargs,
    ) -> tuple[str, str]:
        """Try the requested model, then fall back through available models if auto_fallback is enabled.

        If all models are rate-limited, waits for the rate limit window to reset and retries once.
        """
        models_to_try = [model]
        if auto_fallback and available_models:
            models_to_try += [m for m in available_models if m != model]

        last_error = None

        for attempt in range(_MAX_RETRIES):
            for current_model in models_to_try:
                if log_cb:
                    await log_cb("model_try", f"Trying {_short_name(current_model)}…")
                provider_name, actual_model = _parse_model_id(current_model)
                provider = self.providers.get(provider_name)
                if not provider:
                    if log_cb:
                        await log_cb("model_ratelimited", f"✗ {_short_name(current_model)} — provider not configured")
                    continue
                try:
                    content, _ = await provider.chat(
                        messages=messages, model=actual_model, **kwargs
                    )
                    if log_cb:
                        await log_cb("model_success", f"✓ {_short_name(current_model)}")
                    return content, current_model
                except TooManyRequestsResponseError:
                    logger.warning(f"Model {current_model} rate-limited, trying next...")
                    if log_cb:
                        await log_cb("model_ratelimited", f"✗ {_short_name(current_model)} — rate limited")
                    last_error = RuntimeError(f"Model {current_model} rate-limited")
                    continue
                except Exception as e:
                    if log_cb:
                        await log_cb("model_ratelimited", f"✗ {_short_name(current_model)} — {str(e)[:80]}")
                    last_error = e
                    continue

            if attempt < _MAX_RETRIES - 1:
                logger.info(f"All models rate-limited, waiting {_RETRY_DELAY}s for window reset...")
                if log_cb:
                    await log_cb("model_ratelimited", f"All models rate-limited, waiting {_RETRY_DELAY}s…")
                await asyncio.sleep(_RETRY_DELAY)

        raise last_error or RuntimeError(f"All models rate-limited after {_MAX_RETRIES} attempts")

    async def research(self, event_name: str, event_description: str) -> SearchFindings:
        """Search Tavily for recent information about the event."""
        query = f"{event_name} {event_description}"[:200]
        result = await self.tavily.search(
            query=query,
            search_depth="advanced",
            max_results=5,
            topic="news",
            days=7,
            include_answer=True,
        )
        results = result.get("results", [])
        if not results:
            logger.info("No results for news search, falling back to general search")
            broader_query = event_name.strip()[:200]
            result = await self.tavily.search(
                query=broader_query,
                search_depth="advanced",
                max_results=5,
                topic="general",
                include_answer=True,
            )
            results = result.get("results", [])

        answer = result.get("answer", "")
        return SearchFindings(
            query=query,
            answer=answer,
            results=[
                {"title": r.get("title", ""), "url": r.get("url", ""), "content": r.get("content", ""), "score": r.get("score", 0.0)}
                for r in results
            ],
        )

    async def analyze(
        self,
        findings: SearchFindings,
        event_title: str,
        event_description: str,
        outcomes: list[str],
        model: str,
        auto_fallback: bool = False,
        available_models: list[str] | None = None,
        log_cb=None,
    ) -> AnalysisResult:
        """Analyze search findings using LLM."""
        search_context = ""
        if findings.answer:
            search_context += f"AI summary: {findings.answer}\n\n"
        for i, r in enumerate(findings.results, 1):
            search_context += f"{i}. {r['title']}\n   URL: {r['url']}\n   {r['content']}\n\n"

        system_prompt = (
            "You are an expert prediction analyst. Analyze the following event and identify key factors affecting the outcome. "
            "Respond with valid JSON only. No markdown formatting. No additional text.\n\n"
            "Required JSON format:\n"
            '{"key_factors": ["factor1", "factor2"], "sentiment": "bullish|bearish|neutral", "summary": "brief analysis"}'
        )
        user_prompt = (
            f"Event: {event_title}\n"
            f"Description: {event_description or 'N/A'}\n"
            f"Outcomes: {', '.join(outcomes)}\n\n"
            f"Research findings:\n{search_context}"
        )

        if log_cb:
            await log_cb("analyze_start", "Analyzing findings…")
        content, used_model = await self._call_with_retry(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            model=model,
            auto_fallback=auto_fallback,
            available_models=available_models,
            log_cb=log_cb,
        )
        try:
            data = json.loads(content)
            return AnalysisResult(
                key_factors=data.get("key_factors", []),
                sentiment=data.get("sentiment", "neutral"),
                summary=data.get("summary", ""),
            )
        except (json.JSONDecodeError, KeyError):
            return AnalysisResult(
                key_factors=["Insufficient data for detailed factor analysis"],
                sentiment="neutral",
                summary=content[:500],
            )

    async def predict(
        self,
        analysis: AnalysisResult,
        model: str,
        outcomes: list[str],
        auto_fallback: bool = False,
        available_models: list[str] | None = None,
        log_cb=None,
    ) -> PredictionOutput:
        """Generate prediction using analyzed information and selected model."""
        system_prompt = (
            "You are a prediction analyst. Respond with valid JSON only. No markdown formatting. No additional text.\n\n"
            "Required JSON format:\n"
            '{"probability": 0.75, "verdict": "yes|no|uncertain", "reasoning": "analysis...", "confidence": 0.8}'
        )
        user_prompt = (
            f"Event outcomes: {', '.join(outcomes)}\n"
            f"Key factors: {', '.join(analysis.key_factors)}\n"
            f"Sentiment: {analysis.sentiment}\n"
            f"Analysis: {analysis.summary}\n\n"
            f"Provide a probability (0.0-1.0) for the primary outcome, a verdict (yes/no/uncertain), "
            f"reasoning, and a confidence score (0.0-1.0)."
        )

        if log_cb:
            await log_cb("predict_start", "Generating prediction…")
        content, used_model = await self._call_with_retry(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            model=model,
            auto_fallback=auto_fallback,
            available_models=available_models,
            log_cb=log_cb,
            response_format={"type": "json_object"},
        )
        data = self._parse_prediction_json(content)

        probability = max(0.0, min(1.0, data.get("probability", 0.5)))
        verdict = data.get("verdict", "uncertain")
        if verdict not in ("yes", "no", "uncertain"):
            verdict = "uncertain"

        return PredictionOutput(
            model_name=used_model,
            probability=probability,
            verdict=verdict,
            reasoning=data.get("reasoning", ""),
            sources=[],
            confidence_score=data.get("confidence"),
        )

    def _parse_prediction_json(self, content: str) -> dict:
        """Parse LLM response as JSON, with regex fallback."""
        try:
            return json.loads(content)
        except (json.JSONDecodeError, TypeError):
            logger.warning("LLM returned non-JSON response, using regex fallback")
            prob_match = re.search(r'probability["\s:]+([\d.]+)', content)
            verdict_match = re.search(r'verdict["\s:]+["\']?(yes|no|uncertain)', content, re.IGNORECASE)
            confidence_match = re.search(r'confidence["\s:]+([\d.]+)', content)

            return {
                "probability": float(prob_match.group(1)) if prob_match else 0.5,
                "verdict": verdict_match.group(1).lower() if verdict_match else "uncertain",
                "reasoning": content[:500],
                "confidence": float(confidence_match.group(1)) if confidence_match else None,
            }

    async def generate_forecast(
        self,
        event_title: str,
        event_description: str,
        model: str,
        outcomes: list[str],
        auto_fallback: bool = False,
        available_models: list[str] | None = None,
        log_cb=None,
    ) -> PredictionOutput:
        """End-to-end forecast: research -> analyze -> predict."""
        if log_cb:
            await log_cb("research_start", "Searching for recent news…")
        findings = await self.research(event_title, event_description)
        if log_cb:
            await log_cb("research_done", "✓ News found")
        analysis = await self.analyze(
            findings, event_title, event_description, outcomes, model,
            auto_fallback=auto_fallback, available_models=available_models, log_cb=log_cb,
        )
        return await self.predict(
            analysis, model, outcomes,
            auto_fallback=auto_fallback, available_models=available_models, log_cb=log_cb,
        )
