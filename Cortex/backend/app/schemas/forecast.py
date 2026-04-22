from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ForecastRequest(BaseModel):
    event_id: UUID
    model: str
    auto_fallback: bool = False


class ForecastResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    model_name: str
    probability: float
    predicted_outcome: str | None
    result_status: str
    verdict: str
    reasoning: str
    sources: list[dict]
    confidence_score: float | None
    brier_score: float | None
    created_at: datetime


class AvailableModel(BaseModel):
    id: str
    name: str
    tier: str
    provider: str = ""


class AvailableModelsResponse(BaseModel):
    models: list[AvailableModel]


class PredictionJournalEntry(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    model_name: str
    probability: float
    predicted_outcome: str | None
    result_status: str
    verdict: str
    reasoning: str
    sources: list[dict]
    brier_score: float | None
    created_at: datetime


class PredictionJournalResponse(BaseModel):
    predictions: list[PredictionJournalEntry]


class ModelLeaderboardEntry(BaseModel):
    model_name: str
    total_predictions: int
    resolved_predictions: int
    won_predictions: int
    lost_predictions: int
    win_rate: float | None
    mean_brier_score: float | None
    accuracy: float | None


class OutcomeCheckResponse(BaseModel):
    event_id: UUID
    resolved: bool
    resolved_outcome: str | None
    message: str
    updated_predictions: int = 0


class LeaderboardResponse(BaseModel):
    models: list[ModelLeaderboardEntry]
