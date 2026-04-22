"""LLM provider abstraction for OpenAI-compatible and native chat providers."""

import logging
from abc import ABC, abstractmethod

import httpx
from openrouter import OpenRouter
from openrouter.errors import TooManyRequestsResponseError

logger = logging.getLogger("cortex.agent")


class LLMProvider(ABC):
    """Base class for LLM providers."""

    name: str

    @abstractmethod
    async def chat(self, messages: list[dict], model: str, **kwargs) -> tuple[str, str]:
        """Send chat completion. Returns (content, model_used)."""
        ...


class OpenRouterProvider(LLMProvider):
    name = "openrouter"

    def __init__(self, api_key: str):
        self.client = OpenRouter(
            api_key=api_key,
            async_client=httpx.AsyncClient(follow_redirects=True),
        )

    async def chat(self, messages: list[dict], model: str, **kwargs) -> tuple[str, str]:
        try:
            response = await self.client.chat.send_async(
                messages=messages, model=model, **kwargs
            )
            return response.choices[0].message.content, model
        except TooManyRequestsResponseError:
            raise


class GoogleProvider(LLMProvider):
    """Google AI Studio — OpenAI-compatible endpoint."""

    name = "google"
    BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai"

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            timeout=120.0,
        )

    async def chat(self, messages: list[dict], model: str, **kwargs) -> tuple[str, str]:
        resp = await self.client.post(
            "/chat/completions",
            json={
                "model": model,
                "messages": messages,
                **kwargs,
            },
            params={"key": self.api_key},
        )
        if resp.status_code == 429:
            raise TooManyRequestsResponseError(
                message=f"Google rate limited: {resp.text}",
                response=resp,
                body={"error": resp.text},
            )
        resp.raise_for_status()
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        return content, model


class GroqProvider(LLMProvider):
    """Groq — OpenAI-compatible endpoint."""

    name = "groq"
    BASE_URL = "https://api.groq.com/openai/v1"

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            timeout=120.0,
        )

    async def chat(self, messages: list[dict], model: str, **kwargs) -> tuple[str, str]:
        resp = await self.client.post(
            "/chat/completions",
            json={
                "model": model,
                "messages": messages,
                **kwargs,
            },
        )
        if resp.status_code == 429:
            raise TooManyRequestsResponseError(
                message=f"Groq rate limited: {resp.text}",
                response=resp,
                body={"error": resp.text},
            )
        resp.raise_for_status()
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        return content, model


class DeepSeekProvider(LLMProvider):
    """DeepSeek — OpenAI-compatible endpoint."""

    name = "deepseek"
    BASE_URL = "https://api.deepseek.com/v1"

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            timeout=120.0,
        )

    async def chat(self, messages: list[dict], model: str, **kwargs) -> tuple[str, str]:
        resp = await self.client.post(
            "/chat/completions",
            json={
                "model": model,
                "messages": messages,
                **kwargs,
            },
        )
        if resp.status_code == 429:
            raise TooManyRequestsResponseError(
                message=f"DeepSeek rate limited: {resp.text}",
                response=resp,
                body={"error": resp.text},
            )
        resp.raise_for_status()
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        return content, model


class MistralProvider(LLMProvider):
    """Mistral AI — OpenAI-compatible endpoint."""

    name = "mistral"
    BASE_URL = "https://api.mistral.ai/v1"

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            timeout=120.0,
        )

    async def chat(self, messages: list[dict], model: str, **kwargs) -> tuple[str, str]:
        resp = await self.client.post(
            "/chat/completions",
            json={
                "model": model,
                "messages": messages,
                **kwargs,
            },
        )
        if resp.status_code == 429:
            raise TooManyRequestsResponseError(
                message=f"Mistral rate limited: {resp.text}",
                response=resp,
                body={"error": resp.text},
            )
        resp.raise_for_status()
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        return content, model


class CerebrasProvider(LLMProvider):
    """Cerebras — OpenAI-compatible endpoint (ultra-fast inference)."""

    name = "cerebras"
    BASE_URL = "https://api.cerebras.ai/v1"

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            timeout=120.0,
        )

    async def chat(self, messages: list[dict], model: str, **kwargs) -> tuple[str, str]:
        resp = await self.client.post(
            "/chat/completions",
            json={
                "model": model,
                "messages": messages,
                **kwargs,
            },
        )
        if resp.status_code == 429:
            raise TooManyRequestsResponseError(
                message=f"Cerebras rate limited: {resp.text}",
                response=resp,
                body={"error": resp.text},
            )
        resp.raise_for_status()
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        return content, model


class FireworksProvider(LLMProvider):
    """Fireworks AI — OpenAI-compatible endpoint."""

    name = "fireworks"
    BASE_URL = "https://api.fireworks.ai/inference/v1"

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            timeout=120.0,
        )

    async def chat(self, messages: list[dict], model: str, **kwargs) -> tuple[str, str]:
        resp = await self.client.post(
            "/chat/completions",
            json={
                "model": model,
                "messages": messages,
                **kwargs,
            },
        )
        if resp.status_code == 429:
            raise TooManyRequestsResponseError(
                message=f"Fireworks rate limited: {resp.text}",
                response=resp,
                body={"error": resp.text},
            )
        resp.raise_for_status()
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        return content, model


class NvidiaProvider(LLMProvider):
    """NVIDIA Build / API Catalog — OpenAI-compatible endpoint."""

    name = "nvidia"
    BASE_URL = "https://integrate.api.nvidia.com/v1"

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            timeout=120.0,
        )

    async def chat(self, messages: list[dict], model: str, **kwargs) -> tuple[str, str]:
        resp = await self.client.post(
            "/chat/completions",
            json={
                "model": model,
                "messages": messages,
                **kwargs,
            },
        )
        if resp.status_code == 429:
            raise TooManyRequestsResponseError(
                message=f"NVIDIA rate limited: {resp.text}",
                response=resp,
                body={"error": resp.text},
            )
        resp.raise_for_status()
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        return content, model


def create_providers(
    openrouter_key: str = "",
    google_key: str = "",
    groq_key: str = "",
    deepseek_key: str = "",
    mistral_key: str = "",
    cerebras_key: str = "",
    fireworks_key: str = "",
    nvidia_key: str = "",
) -> dict[str, LLMProvider]:
    """Create provider instances from config keys. Only includes providers with valid keys."""
    providers: dict[str, LLMProvider] = {}
    if openrouter_key:
        providers["openrouter"] = OpenRouterProvider(openrouter_key)
    if google_key:
        providers["google"] = GoogleProvider(google_key)
    if groq_key:
        providers["groq"] = GroqProvider(groq_key)
    if deepseek_key:
        providers["deepseek"] = DeepSeekProvider(deepseek_key)
    if mistral_key:
        providers["mistral"] = MistralProvider(mistral_key)
    if cerebras_key:
        providers["cerebras"] = CerebrasProvider(cerebras_key)
    if fireworks_key:
        providers["fireworks"] = FireworksProvider(fireworks_key)
    if nvidia_key:
        providers["nvidia"] = NvidiaProvider(nvidia_key)
    return providers
