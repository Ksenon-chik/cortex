from pydantic import BaseModel, ConfigDict


class UserApiKeyCreate(BaseModel):
    provider: str  # "openrouter", "google", "groq"
    api_key: str


class UserApiKeyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    provider: str
    is_active: bool
    created_at: str
