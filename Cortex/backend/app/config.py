import json
import logging
from base64 import urlsafe_b64decode
from base64 import urlsafe_b64encode
from hashlib import sha256
from typing import Optional

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


logger = logging.getLogger("cortex.config")


NVIDIA_FREE_MODELS = [
    # NVIDIA-owned free text/chat models from the public API catalog.
    "nvidia:nvidia/cosmos-reason2-8b",
    "nvidia:nvidia/llama-3.1-nemotron-51b-instruct",
    "nvidia:nvidia/llama-3.1-nemotron-70b-instruct",
    "nvidia:nvidia/llama-3.1-nemotron-nano-8b-v1",
    "nvidia:nvidia/llama-3.1-nemotron-ultra-253b-v1",
    "nvidia:nvidia/llama-3.3-nemotron-super-49b-v1.5",
    "nvidia:nvidia/llama3-chatqa-1.5-70b",
    "nvidia:nvidia/mistral-nemo-minitron-8b-8k-instruct",
    "nvidia:nvidia/nemotron-3-nano-30b-a3b",
    "nvidia:nvidia/nemotron-3-super-120b-a12b",
    "nvidia:nvidia/nemotron-4-340b-instruct",
    "nvidia:nvidia/nemotron-mini-4b-instruct",
    "nvidia:nvidia/nemotron-nano-3-30b-a3b",
    "nvidia:nvidia/nvidia-nemotron-nano-9b-v2",
]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@db:5432/cortex"

    @field_validator("database_url", mode="before")
    @classmethod
    def ensure_asyncpg_dialect(cls, v: str) -> str:
        """Переводит стандартные URL Postgres в формат asyncpg для Railway."""
        if isinstance(v, str):
            v = v.replace("postgres://", "postgresql://", 1)
            if v.startswith("postgresql://"):
                v = v.replace("postgresql://", "postgresql+asyncpg://", 1)
        return v

    # API Endpoints
    polymarket_gamma_api_url: str = "https://gamma-api.polymarket.com"
    polymarket_clob_api_url: str = "https://clob.polymarket.com"
    
    # Kalshi API URLs
    kalshi_api_url: str = "https://api.kalshi.com/trade-api/v2"
    kalshi_demo_api_url: str = "https://demo-api.kalshi.co/trade-api/v2"

    # CORS
    # По умолчанию localhost, в Railway нужно переопределить через переменную
    cors_origins: list[str] = ["http://localhost:3000"]

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        """Парсит строку ["url1", "url2"] из переменных окружения в Python list."""
        if isinstance(v, str):
            try:
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    return parsed
            except json.JSONDecodeError:
                return [v]
        return v

    # External Services
    db_pool_size: int = 5
    db_max_overflow: int = 10

    # Models Configuration — multi-provider models with provider prefix
    available_models: list[str] = [
        # OpenRouter free models
        "openrouter:google/gemma-4-31b-it:free",
        "openrouter:google/gemma-3-27b-it:free",
        "openrouter:meta-llama/llama-3.3-70b-instruct:free",
        "openrouter:qwen/qwen3-next-80b-a3b-instruct:free",
        "openrouter:minimax/minimax-m2.5:free",
        "openrouter:nousresearch/hermes-3-llama-3.1-405b:free",
        "openrouter:nvidia/nemotron-3-super-120b-a12b:free",
        "openrouter:openai/gpt-oss-120b:free",
        "openrouter:z-ai/glm-4.5-air:free",
        "openrouter:qwen/qwen3-coder:free",
        # Google AI Studio
        "google:gemini-2.0-flash",
        "google:gemini-2.0-flash-lite",
        # Groq
        "groq:llama-3.3-70b-versatile",
        "groq:mixtral-8x7b-32768",
        "groq:llama-3.1-8b-instant",
        # DeepSeek
        "deepseek:deepseek-chat",
        "deepseek:deepseek-reasoner",
        # Mistral
        "mistral:mistral-small-latest",
        "mistral:mistral-large-latest",
        # Cerebras
        "cerebras:llama3.1-70b",
        "cerebras:llama3.3-70b",
        # Fireworks
        "fireworks:accounts/fireworks/models/llama-v3p1-70b-instruct",
        "fireworks:accounts/fireworks/models/mixtral-8x7b-instruct",
        # NVIDIA Build / API Catalog (free text models via public /v1/models catalog)
        *NVIDIA_FREE_MODELS,
    ]

    @field_validator("available_models", mode="before")
    @classmethod
    def parse_models(cls, v):
        """Позволяет менять список моделей через Railway Variables без правки кода."""
        if isinstance(v, str):
            try:
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    return parsed
            except json.JSONDecodeError:
                return [v]
        return v

    # Authentication
    jwt_secret: str = "change-me-in-production-very-secret-key"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60
    jwt_refresh_token_expire_days: int = 7
    api_key_encryption_key: str = ""

    cookie_name: str = "cortex_access_token"
    cookie_domain: Optional[str] = None
    cookie_secure: bool = True

    auth_rate_limit_attempts: int = 10
    auth_rate_limit_window_seconds: int = 300
    forecast_rate_limit_attempts: int = 10
    forecast_rate_limit_window_seconds: int = 60

    # Business Logic
    daily_forecast_limit_free: int = 5

    @field_validator("jwt_secret")
    @classmethod
    def validate_jwt_secret(cls, value: str) -> str:
        if not value:
            raise ValueError("JWT_SECRET must not be empty")
        return value

    @model_validator(mode="after")
    def finalize_security_settings(self):
        if not self.api_key_encryption_key:
            self.api_key_encryption_key = urlsafe_b64encode(
                sha256(
                    b"cortex-api-key-encryption:" +
                    self.jwt_secret.encode("utf-8")
                ).digest()
            ).decode("utf-8")
            logger.warning(
                "API_KEY_ENCRYPTION_KEY is not configured; deriving it from JWT_SECRET for backward compatibility"
            )
        if self.jwt_secret == "change-me-in-production-very-secret-key":
            logger.warning(
                "JWT_SECRET is using the default insecure fallback; set a strong secret in production"
            )

        value = self.api_key_encryption_key
        try:
            raw = urlsafe_b64decode(value.encode("utf-8"))
        except Exception as err:  # pragma: no cover - validator safety
            raise ValueError(
                "API_KEY_ENCRYPTION_KEY must be a valid Fernet key"
            ) from err
        if len(raw) != 32:
            raise ValueError(
                "API_KEY_ENCRYPTION_KEY must decode to 32 bytes"
            )
        return self


settings = Settings()
