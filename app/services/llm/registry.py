from __future__ import annotations

from functools import lru_cache

from app.config import get_settings

from .openai_provider import OpenAIProvider
from .base import LLMProvider

_PROVIDERS: dict[str, type[LLMProvider]] = {
    "openai": OpenAIProvider,
    # future: "anthropic": AnthropicProvider,
}


@lru_cache()
def get_provider() -> LLMProvider:
    settings = get_settings()
    provider_key = settings.llm_provider.lower()
    if provider_key not in _PROVIDERS:
        raise ValueError(f"Unsupported LLM provider: {provider_key}")
    return _PROVIDERS[provider_key]() 