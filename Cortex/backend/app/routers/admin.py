import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select, update, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func

from app.constants.categories import detect_category
from app.database import get_db
from app.models.event import Event
from app.models.user import User
from app.config import settings
from app.schemas.user import AdminUserResponse, AdminModelItem, AdminModelsResponse, AdminModelsUpdate
from app.schemas.event import EventResponse
from app.services.csrf import validate_csrf
from app.services.dependencies import get_admin_user

router = APIRouter()

_get_db = Depends(get_db)


@router.get("/users", response_model=list[AdminUserResponse])
async def list_all_users(
    db: AsyncSession = _get_db,
    _admin: User = Depends(get_admin_user),  # noqa: B008
):
    """List all registered users. Requires admin."""
    result = await db.execute(select(User).order_by(User.created_at.desc()))
    users = result.scalars().all()
    return [AdminUserResponse.model_validate(u) for u in users]


@router.get("/users/pending", response_model=list[AdminUserResponse])
async def list_pending_users(
    db: AsyncSession = _get_db,
    _admin: User = Depends(get_admin_user),  # noqa: B008
):
    """List users who are active but not yet whitelisted. Requires admin."""
    result = await db.execute(
        select(User)
        .where(User.is_active.is_(True), User.whitelisted.is_(False))
        .order_by(User.created_at.asc())
    )
    users = result.scalars().all()
    return [AdminUserResponse.model_validate(u) for u in users]


@router.post("/users/{user_id}/whitelist", response_model=AdminUserResponse)
async def whitelist_user(
    user_id: uuid.UUID,
    db: AsyncSession = _get_db,
    _admin: User = Depends(get_admin_user),  # noqa: B008
    _csrf: None = Depends(validate_csrf),  # noqa: B008
):
    """Approve (whitelist) a user. Requires admin."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.whitelisted = True
    await db.commit()
    await db.refresh(user)
    return AdminUserResponse.model_validate(user)


@router.post("/users/{user_id}/reject", response_model=AdminUserResponse)
async def reject_user(
    user_id: uuid.UUID,
    db: AsyncSession = _get_db,
    _admin: User = Depends(get_admin_user),  # noqa: B008
    _csrf: None = Depends(validate_csrf),  # noqa: B008
):
    """Reject a user: remove whitelist and deactivate their account. Requires admin."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.whitelisted = False
    user.is_active = False
    await db.commit()
    await db.refresh(user)
    return AdminUserResponse.model_validate(user)


@router.post("/promote/{user_id}", response_model=AdminUserResponse)
async def promote_user(
    user_id: uuid.UUID,
    db: AsyncSession = _get_db,
    admin: User = Depends(get_admin_user),  # noqa: B008
    _csrf: None = Depends(validate_csrf),  # noqa: B008
):
    """Grant admin privileges to a user. Requires admin."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.id == admin.id:
        raise HTTPException(
            status_code=400, detail="Cannot modify your own admin status"
        )

    user.is_admin = True
    await db.commit()
    await db.refresh(user)
    return AdminUserResponse.model_validate(user)


_MODEL_NAMES: dict[str, str] = {
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
    # DeepSeek
    "deepseek:deepseek-chat": "DeepSeek V3",
    "deepseek:deepseek-reasoner": "DeepSeek R1",
    # Mistral
    "mistral:mistral-small-latest": "Mistral Small",
    "mistral:mistral-large-latest": "Mistral Large",
    # Cerebras
    "cerebras:llama3.1-70b": "Llama 3.1 70B",
    "cerebras:llama3.3-70b": "Llama 3.3 70B",
    # Fireworks
    "fireworks:accounts/fireworks/models/llama-v3p1-70b-instruct": "Llama 3.1 70B",
    "fireworks:accounts/fireworks/models/mixtral-8x7b-instruct": "Mixtral 8x7B",
    # NVIDIA
    "nvidia:nvidia/nemotron-3-super-120b-a12b": "Nemotron 3 Super 120B",
    "nvidia:nvidia/nemotron-4-340b-instruct": "Nemotron 4 340B",
    "nvidia:nvidia/llama-3.3-nemotron-super-49b-v1.5": "Llama 3.3 Nemotron Super 49B",
    "nvidia:openai/gpt-oss-120b": "GPT-OSS 120B",
    "nvidia:openai/gpt-oss-20b": "GPT-OSS 20B",
}

_VALID_PROVIDERS = {"openrouter", "google", "groq", "deepseek", "mistral", "cerebras", "fireworks", "nvidia"}


def _parse_model(model_id: str) -> AdminModelItem:
    provider = model_id.split(":")[0] if ":" in model_id else "unknown"
    tier = "free" if model_id.endswith(":free") or provider in ("google", "groq", "deepseek", "cerebras", "nvidia") else "premium"
    return AdminModelItem(
        id=model_id,
        name=_MODEL_NAMES.get(model_id, model_id.split(":")[-1].split("/")[-1].replace(":free", "").replace("-", " ").title()),
        tier=tier,
        provider=provider,
    )


@router.get("/models", response_model=AdminModelsResponse)
async def list_models(
    _admin: User = Depends(get_admin_user),  # noqa: B008
):
    """Return current available models. Requires admin."""
    return AdminModelsResponse(
        models=[_parse_model(m) for m in settings.available_models]
    )


@router.post("/models", response_model=AdminModelsResponse)
async def update_models(
    body: AdminModelsUpdate,
    _admin: User = Depends(get_admin_user),  # noqa: B008
    _csrf: None = Depends(validate_csrf),  # noqa: B008
):
    """Update the list of available models. Requires admin. Only known providers allowed."""
    for model_id in body.models:
        provider = model_id.split(":")[0] if ":" in model_id else ""
        if provider not in _VALID_PROVIDERS:
            raise HTTPException(
                status_code=400,
                detail=f"Model '{model_id}' has unknown provider '{provider}'. Allowed: {', '.join(sorted(_VALID_PROVIDERS))}",
            )
    settings.available_models = body.models
    return AdminModelsResponse(
        models=[_parse_model(m) for m in settings.available_models]
    )


@router.post("/backfill-categories")
async def backfill_categories(
    db: AsyncSession = _get_db,
    _admin: User = Depends(get_admin_user),  # noqa: B008
    _csrf: None = Depends(validate_csrf),  # noqa: B008
):
    """Detect and fill category_normalized for all existing events. Requires admin."""
    result = await db.execute(select(Event))
    events = result.scalars().all()

    updated = 0
    for event in events:
        cat = detect_category(event.title, event.description or "")
        await db.execute(
            update(Event)
            .where(Event.id == event.id)
            .values(category=cat, category_normalized=cat)
        )
        updated += 1

    await db.commit()
    return {"updated": updated, "total": len(events)}


@router.get("/polymarket/search")
async def search_polymarket(
    request: Request,
    q: str = Query(default="", description="Search query"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    sort: str = Query(default="none", pattern="^(none|soonest|latest)$"),
    deadline_filter: str = Query(default="all", pattern="^(all|with_deadline|without_deadline)$"),
    _admin: User = Depends(get_admin_user),  # noqa: B008
):
    """Search Polymarket markets (read-only, no DB save). Requires admin."""
    poly_client = request.app.state.poly_client
    markets, total = await poly_client.search_markets(
        q=q,
        limit=limit,
        offset=offset,
        sort=sort,
        deadline_filter=deadline_filter,
    )
    return {
        "items": [
            {
                "id": m.id,
                "question": m.question,
                "description": m.description,
                "active": m.active,
                "closed": m.closed,
                "end_date": m.end_date,
            }
            for m in markets
        ],
        "total": total,
    }


@router.post("/events/add/{market_id}", response_model=EventResponse)
async def add_event_to_db(
    market_id: str,
    request: Request,
    db: AsyncSession = _get_db,
    _admin: User = Depends(get_admin_user),  # noqa: B008
    _csrf: None = Depends(validate_csrf),  # noqa: B008
):
    """Add a specific Polymarket market to the local DB. Requires admin."""
    poly_client = request.app.state.poly_client
    market = await poly_client.fetch_market(market_id)
    if not market:
        raise HTTPException(status_code=404, detail="Market not found on Polymarket")

    from app.services.sync import gamma_market_to_event

    event_data = gamma_market_to_event(market)
    stmt = insert(Event).values(**event_data)
    stmt = stmt.on_conflict_do_update(
        index_elements=["polymarket_market_id"],
        set_={
            "title": stmt.excluded.title,
            "description": stmt.excluded.description,
            "category": stmt.excluded.category,
            "category_normalized": stmt.excluded.category_normalized,
            "outcomes": stmt.excluded.outcomes,
            "outcome_prices": stmt.excluded.outcome_prices,
            "active": stmt.excluded.active,
            "closed": stmt.excluded.closed,
            "end_date": stmt.excluded.end_date,
            "updated_at": func.now(),
        },
    )
    await db.execute(stmt)
    await db.commit()

    result = await db.execute(select(Event).where(Event.polymarket_market_id == market_id))
    event = result.scalar_one()
    return EventResponse.model_validate(event)


@router.post("/events/truncate")
async def truncate_events(
    db: AsyncSession = _get_db,
    _admin: User = Depends(get_admin_user),  # noqa: B008
    _csrf: None = Depends(validate_csrf),  # noqa: B008
):
    """Truncate all events from the database. Requires admin."""
    await db.execute(text("TRUNCATE TABLE events CASCADE"))
    await db.commit()
    return {"status": "ok", "message": "All events truncated"}


@router.post("/events/resync/{event_id}", response_model=EventResponse)
async def resync_event(
    event_id: uuid.UUID,
    request: Request,
    db: AsyncSession = _get_db,
    _admin: User = Depends(get_admin_user),  # noqa: B008
    _csrf: None = Depends(validate_csrf),  # noqa: B008
):
    """Resync a single event from Polymarket. Requires admin."""
    result = await db.execute(select(Event).where(Event.id == event_id))
    event = result.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found in local DB")

    poly_client = request.app.state.poly_client
    market = await poly_client.fetch_market(event.polymarket_market_id)
    if not market:
        raise HTTPException(status_code=404, detail="Market not found on Polymarket")

    from app.services.sync import gamma_market_to_event

    event_data = gamma_market_to_event(market)
    stmt = (
        update(Event)
        .where(Event.id == event_id)
        .values(**event_data, updated_at=func.now())
    )
    await db.execute(stmt)
    await db.commit()

    await db.refresh(event)
    return EventResponse.model_validate(event)


def _format_bytes(n: int) -> str:
    if n < 1024:
        return f"{n} B"
    if n < 1024 * 1024:
        return f"{n / 1024:.1f} KB"
    if n < 1024 * 1024 * 1024:
        return f"{n / (1024 * 1024):.1f} MB"
    return f"{n / (1024 * 1024 * 1024):.2f} GB"


@router.get("/db-size")
async def get_database_size(
    db: AsyncSession = _get_db,
    _admin: User = Depends(get_admin_user),  # noqa: B008
):
    """Return database total size, per-table breakdown, and all events with sizes. Requires admin."""
    # Total DB size
    result = await db.execute(text(
        "SELECT pg_database_size(current_database())"
    ))
    total_bytes = result.scalar() or 0

    # Per-table size
    result = await db.execute(text("""
        SELECT
            relname AS table_name,
            pg_total_relation_size(oid) AS size_bytes
        FROM pg_class
        WHERE relkind = 'r'
          AND relnamespace = (SELECT oid FROM pg_namespace WHERE nspname = 'public')
        ORDER BY size_bytes DESC
    """))
    tables = [{"table": row[0], "size": _format_bytes(row[1]), "size_bytes": row[1]} for row in result.all()]

    # All events with sizes
    result = await db.execute(text("""
        SELECT id, polymarket_market_id, title, category_normalized, active, closed, end_date,
               pg_column_size(events.*) AS row_bytes
        FROM events
        ORDER BY row_bytes DESC
    """))
    events = [{
        "id": str(row[0]),
        "polymarket_market_id": row[1],
        "title": row[2],
        "category_normalized": row[3],
        "active": row[4],
        "closed": row[5],
        "end_date": row[6],
        "size": _format_bytes(row[7]),
        "size_bytes": row[7],
    } for row in result.all()]

    return {
        "total_size": _format_bytes(total_bytes),
        "total_bytes": total_bytes,
        "tables": tables,
        "events": events,
    }


@router.delete("/events/{event_id}")
async def delete_event(
    event_id: uuid.UUID,
    db: AsyncSession = _get_db,
    _admin: User = Depends(get_admin_user),  # noqa: B008
    _csrf: None = Depends(validate_csrf),  # noqa: B008
):
    """Delete a single event from the database. Requires admin."""
    result = await db.execute(select(Event).where(Event.id == event_id))
    event = result.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    await db.delete(event)
    await db.commit()
    return {"status": "ok", "message": f"Event '{event.title[:50]}' deleted"}
