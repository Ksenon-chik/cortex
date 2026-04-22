from pydantic import BaseModel, Field


class SearchFindings(BaseModel):
    query: str
    answer: str = ""
    results: list[dict] = Field(default_factory=list)


class AnalysisResult(BaseModel):
    key_factors: list[str] = Field(default_factory=list)
    sentiment: str = "neutral"
    summary: str = ""


class PredictionOutput(BaseModel):
    model_name: str
    probability: float = Field(ge=0.0, le=1.0)
    verdict: str
    reasoning: str
    sources: list[dict] = Field(default_factory=list)
    confidence_score: float | None = None
