from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class EventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    polymarket_market_id: str
    title: str
    description: str | None
    category: str
    category_normalized: str
    outcomes: list
    outcome_prices: dict
    active: bool
    closed: bool
    end_date: datetime | None
    resolved_outcome: str | None
    created_at: datetime
    updated_at: datetime
