import asyncio
import json
import logging
import uuid
from typing import AsyncGenerator, Dict

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import case, select, func as sa_func
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.forecast import PredictionAgent
from app.agents.providers import create_providers
from app.config import settings
from app.database import get_db
from app.models.event import Event
from app.models.prediction import Prediction
from app.models.user import User
from app.models.user_api_key import UserApiKey
from app.schemas.forecast import (
    AvailableModel,
    AvailableModelsResponse,
    ForecastRequest,
    ForecastResponse,
    LeaderboardResponse,
    ModelLeaderboardEntry,
    OutcomeCheckResponse,
    PredictionJournalEntry,
    PredictionJournalResponse,
)
from app.services.crypto import decrypt_api_key
from app.services.csrf import validate_csrf
from app.services.dependencies import get_current_user
from app.services.quota import check_forecast_quota
from app.services.rate_limit import enforce_rate_limit
from app.services.resolution import (
    _determine_winner,
    determine_predicted_outcome,
    resolve_event_by_market_id,
)

logger = logging.getLogger("cortex.agent")
router = APIRouter()

# Словарь для красивых названий моделей
_MODEL_NAMES: Dict[str, str] = {
    # OpenRouter
    "openrouter:google/gemma-4-31b-it:free": "Gemma 4 31B",
    "openrouter:google/gemma-3-27b-it:free": "Gemma 3 27B",
    "openrouter:meta-llama/llama-3.3-70b-instruct:free": "Llama 3.3 70B",
    "openrouter:qwen/qwen3-next-80b-a3b-instruct:free": "Qwen3 Next 80B",
    "openrouter:minimax/minimax-m2.5:free": "MiniMax M2.5",
    "openrouter:nousresearch/hermes-3-llama-3.1-405b:free": "Hermes 3 405B",
    "openrouter:nvidia/nemotron-3-super-120b-a12b:free": "Nemotron 3 Super 120B",
    "openrouter:openai/gpt-oss-120b:free": "GPT-OSS 120B",
    "openrouter:z-ai/glm-4.5-air:free": "GLM 4.5 Air",
    "openrouter:qwen/qwen3-coder:free": "Qwen3 Coder",
    # Google AI Studio
    "google:gemini-2.0-flash": "Gemini 2.0 Flash",
    "google:gemini-2.0-flash-lite": "Gemini 2.0 Flash Lite",
    # Groq
    "groq:llama-3.3-70b-versatile": "Llama 3.3 70B",
    "groq:mixtral-8x7b-32768": "Mixtral 8x7B",
    "groq:llama-3.1-8b-instant": "Llama 3.1 8B",
    # NVIDIA
    "nvidia:nvidia/nemotron-3-super-120b-a12b": "Nemotron 3 Super 120B",
    "nvidia:nvidia/nemotron-4-340b-instruct": "Nemotron 4 340B",
    "nvidia:nvidia/llama-3.3-nemotron-super-49b-v1.5": "Llama 3.3 Nemotron Super 49B",
    "nvidia:openai/gpt-oss-120b": "GPT-OSS 120B",
    "nvidia:openai/gpt-oss-20b": "GPT-OSS 20B",
}

@router.get("/models", response_model=AvailableModelsResponse)
async def get_available_models():
    """Список доступных LLM моделей."""
    models = []
    for model_id in settings.available_models:
        provider = model_id.split(":")[0] if ":" in model_id else "unknown"
        models.append(
            AvailableModel(
                id=model_id,
                name=_MODEL_NAMES.get(model_id, model_id.split(":")[-1]),
                tier="free",
                provider=provider,
            )
        )
    return AvailableModelsResponse(models=models)


@router.get("/{event_id}/predictions", response_model=PredictionJournalResponse)
async def get_event_predictions(
    event_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Получить все прогнозы для события. 
    Путь исправлен на /{event_id}/predictions для устранения 404.
    """
    # Проверяем, существует ли событие
    event_result = await db.execute(select(Event).where(Event.id == event_id))
    if not event_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Event not found")

    # Получаем прогнозы
    result = await db.execute(
        select(Prediction)
        .where(Prediction.event_id == event_id)
        .order_by(Prediction.created_at.desc())
    )
    predictions = result.scalars().all()

    entries = [PredictionJournalEntry.model_validate(p) for p in predictions]
    return PredictionJournalResponse(predictions=entries)


@router.post("/stream")
async def generate_forecast_stream(
    body: ForecastRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    _csrf: None = Depends(validate_csrf),  # noqa: B008
):
    """Генерация нового прогноза через ИИ-агента с SSE-стримингом логов."""
    await enforce_rate_limit(
        request,
        "forecast:stream",
        settings.forecast_rate_limit_attempts,
        settings.forecast_rate_limit_window_seconds,
        actor=str(user.id),
    )
    event_id = body.event_id
    model = body.model
    auto_fallback = body.auto_fallback
    if model not in settings.available_models:
        raise HTTPException(status_code=400, detail=f"Model {model} not available")

    await check_forecast_quota(db, user, settings.daily_forecast_limit_free)

    event_result = await db.execute(select(Event).where(Event.id == event_id))
    event = event_result.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    # Look up user's API keys
    user_keys_result = await db.execute(
        select(UserApiKey).where(
            UserApiKey.user_id == user.id,
            UserApiKey.is_active.is_(True),
        )
    )
    user_keys: dict[str, str] = {}
    for key in user_keys_result.scalars().all():
        try:
            user_keys[key.provider] = decrypt_api_key(key.api_key)
        except ValueError:
            logger.warning("Skipping undecryptable API key for provider %s", key.provider)

    missing = []
    llm_providers = {"openrouter", "google", "groq", "deepseek", "mistral", "cerebras", "fireworks", "nvidia"}
    has_llm = any(user_keys.get(p) for p in llm_providers)
    if not has_llm:
        missing.append("at least one LLM provider (openrouter, google, groq, deepseek, mistral, cerebras, fireworks, or nvidia)")
    if not user_keys.get("tavily"):
        missing.append("tavily")

    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"API keys not configured. Please add {', '.join(missing)} in your profile.",
        )

    providers = create_providers(
        openrouter_key=user_keys.get("openrouter", ""),
        google_key=user_keys.get("google", ""),
        groq_key=user_keys.get("groq", ""),
        deepseek_key=user_keys.get("deepseek", ""),
        mistral_key=user_keys.get("mistral", ""),
        cerebras_key=user_keys.get("cerebras", ""),
        fireworks_key=user_keys.get("fireworks", ""),
        nvidia_key=user_keys.get("nvidia", ""),
    )
    if not providers:
        logger.error("No LLM providers configured for user")
        raise HTTPException(status_code=500, detail="LLM Provider not configured")

    queue: asyncio.Queue = asyncio.Queue()

    async def log_cb(event_type: str, message: str):
        await queue.put({"event": event_type, "data": message})

    async def event_stream() -> AsyncGenerator[str, None]:
        agent = PredictionAgent(
            tavily_api_key=user_keys["tavily"],
            providers=providers,
        )

        # Start the forecast task in background
        async def run_forecast():
            try:
                prediction_output = await agent.generate_forecast(
                    event_title=event.title,
                    event_description=event.description or "",
                    model=model,
                    outcomes=event.outcomes,
                    auto_fallback=auto_fallback,
                    available_models=settings.available_models,
                    log_cb=log_cb,
                )

                prediction = Prediction(
                    event_id=event_id,
                    model_name=prediction_output.model_name,
                    probability=prediction_output.probability,
                    predicted_outcome=determine_predicted_outcome(
                        verdict=prediction_output.verdict,
                        probability=prediction_output.probability,
                        outcomes=event.outcomes,
                    ),
                    result_status="pending",
                    verdict=prediction_output.verdict,
                    reasoning=prediction_output.reasoning,
                    sources=prediction_output.sources,
                    confidence_score=prediction_output.confidence_score,
                    user_id=user.id,
                )
                db.add(prediction)
                await db.commit()
                await db.refresh(prediction)

                await queue.put({
                    "event": "result",
                    "data": ForecastResponse.model_validate(prediction).model_dump_json(),
                })
            except Exception as e:
                logger.exception(f"Forecast generation failed for model {model}")
                await queue.put(
                    {
                        "event": "error",
                        "data": "Forecast generation failed. Please try again later.",
                    }
                )
            finally:
                await queue.put({"event": "end", "data": ""})

        task = asyncio.create_task(run_forecast())

        # Stream log events as they arrive
        while True:
            msg = await queue.get()
            yield f"event: {msg['event']}\ndata: {json.dumps(msg['data'])}\n\n"
            if msg["event"] == "end":
                break

        await task

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/{event_id}/check-outcome", response_model=OutcomeCheckResponse)
async def check_event_outcome(
    event_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
    _csrf: None = Depends(validate_csrf),  # noqa: B008
):
    event_result = await db.execute(select(Event).where(Event.id == event_id))
    event = event_result.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    poly_client = request.app.state.poly_client
    market = await poly_client.fetch_market(event.polymarket_market_id)
    if not market:
        raise HTTPException(status_code=404, detail="Market not found on Polymarket")

    winning_outcome = _determine_winner(market.outcomes, market.outcome_prices)
    if not market.closed or not winning_outcome:
        return OutcomeCheckResponse(
            event_id=event.id,
            resolved=False,
            resolved_outcome=event.resolved_outcome,
            message="Outcome is not resolved yet.",
            updated_predictions=0,
        )

    updated_predictions = await resolve_event_by_market_id(
        session=db,
        market_id=market.id,
        winning_outcome=winning_outcome,
    )
    await db.commit()

    return OutcomeCheckResponse(
        event_id=event.id,
        resolved=True,
        resolved_outcome=winning_outcome,
        message="Outcome resolved and predictions updated.",
        updated_predictions=updated_predictions,
    )


@router.get("/leaderboard", response_model=LeaderboardResponse)
async def get_leaderboard(
    db: AsyncSession = Depends(get_db),
):
    """Рейтинг моделей на основе Brier Score."""
    # Статистика по решенным прогнозам
    result = await db.execute(
        select(
            Prediction.model_name,
            sa_func.count(Prediction.id).label("total_predictions"),
            sa_func.count(Prediction.brier_score).label("resolved_predictions"),
            sa_func.sum(
                case((Prediction.result_status == "won", 1), else_=0)
            ).label("won_predictions"),
            sa_func.sum(
                case((Prediction.result_status == "lost", 1), else_=0)
            ).label("lost_predictions"),
            sa_func.avg(Prediction.brier_score).label("mean_brier_score"),
        )
        .where(Prediction.brier_score.isnot(None))
        .group_by(Prediction.model_name)
        .order_by(sa_func.avg(Prediction.brier_score).asc())
    )
    rows = result.all()

    # Общее количество прогнозов (включая нерешенные)
    total_result = await db.execute(
        select(
            Prediction.model_name,
            sa_func.count(Prediction.id).label("total_count"),
        )
        .group_by(Prediction.model_name)
    )
    totals = {r.model_name: r.total_count for r in total_result.all()}

    models_stats = []
    for row in rows:
        models_stats.append(
            ModelLeaderboardEntry(
                model_name=row.model_name,
                total_predictions=totals.get(row.model_name, row.total_predictions),
                resolved_predictions=row.resolved_predictions,
                won_predictions=int(row.won_predictions or 0),
                lost_predictions=int(row.lost_predictions or 0),
                win_rate=(
                    round(float((row.won_predictions or 0) / row.resolved_predictions), 4)
                    if row.resolved_predictions
                    else None
                ),
                mean_brier_score=round(float(row.mean_brier_score), 4) if row.mean_brier_score else None,
                accuracy=(
                    round(float((row.won_predictions or 0) / row.resolved_predictions), 4)
                    if row.resolved_predictions
                    else None
                ),
            )
        )

    return LeaderboardResponse(models=models_stats)
