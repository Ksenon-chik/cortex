import json

from pydantic import BaseModel, ConfigDict, Field, field_validator


class GammaMarket(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    question: str
    description: str = ""
    category: str = ""
    outcomes: list[str] = Field(default_factory=list)
    outcome_prices: list[float] = Field(alias="outcomePrices", default_factory=list)
    active: bool = True
    closed: bool = False
    end_date: str | None = Field(alias="endDate", default=None)
    slug: str | None = None
    tags: list[str] | None = None

    @field_validator("outcomes", "outcome_prices", mode="before")
    @classmethod
    def parse_json_string(cls, v):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except (json.JSONDecodeError, ValueError):
                return []
        return v

    @field_validator("outcome_prices", mode="after")
    @classmethod
    def coerce_prices(cls, v):
        if isinstance(v, list):
            result = []
            for item in v:
                try:
                    result.append(float(item))
                except (ValueError, TypeError):
                    result.append(0.0)
            return result
        return v

    @field_validator("tags", mode="before")
    @classmethod
    def parse_tags(cls, v):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except (json.JSONDecodeError, ValueError):
                return None
        return v


class GammaEvent(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    title: str
    description: str | None = None
    slug: str | None = None
    markets: list[GammaMarket] | None = None


class ClobPrice(BaseModel):
    model_config = ConfigDict(extra="ignore")

    asset_id: str
    price: float
    timestamp: str | None = None
