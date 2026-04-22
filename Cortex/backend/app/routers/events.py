from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.event import Event
from app.schemas.event import EventResponse
from app.schemas.pagination import PaginatedResponse

router = APIRouter()

_get_db = Depends(get_db)


@router.get("/categories")
async def list_categories(
    db: AsyncSession = _get_db,
):
    """Return sorted list of unique normalized event categories."""
    result = await db.execute(
        select(Event.category_normalized).distinct().order_by(Event.category_normalized)
    )
    categories = [row[0] for row in result.all() if row[0]]
    return {"categories": categories}


@router.get("", response_model=PaginatedResponse[EventResponse])
async def list_events(
    page: int = Query(ge=1, default=1),
    page_size: int = Query(ge=1, le=100, default=20),
    category: str | None = Query(default=None),
    search: str | None = Query(default=None),
    db: AsyncSession = _get_db,
):
    """List events with pagination, optional category filter, and optional text search."""
    # Build base query
    query = select(Event)
    count_query = select(func.count(Event.id))

    if category:
        query = query.where(Event.category_normalized == category)
        count_query = count_query.where(Event.category_normalized == category)

    if search:
        pattern = f"%{search}%"
        search_filter = Event.title.ilike(pattern) | Event.description.ilike(pattern)
        query = query.where(search_filter)
        count_query = count_query.where(search_filter)

    # Get total count
    total_result = await db.execute(count_query)
    total = total_result.scalar_one()

    # Get paginated items
    offset = (page - 1) * page_size
    query = query.order_by(Event.created_at.desc()).limit(page_size).offset(offset)
    result = await db.execute(query)
    events = result.scalars().all()

    items = [EventResponse.model_validate(e) for e in events]

    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        has_next=(offset + page_size) < total,
        has_prev=page > 1,
    )


@router.get("/{event_id}", response_model=EventResponse)
async def get_event(
    event_id: str,
    db: AsyncSession = _get_db,
):
    """Get single event by ID."""
    from uuid import UUID

    try:
        event_uuid = UUID(event_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Invalid event ID format") from e

    result = await db.execute(select(Event).where(Event.id == event_uuid))
    event = result.scalar_one_or_none()

    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    return EventResponse.model_validate(event)
