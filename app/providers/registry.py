import httpx
from fastapi import HTTPException

from app.providers.anthropic import AnthropicProvider
from app.providers.base import BaseProvider
from app.providers.groq import GroqProvider
from app.providers.openai import OpenAIProvider

PROVIDERS: dict[str, type[BaseProvider]] = {
    "openai": OpenAIProvider,
    "groq": GroqProvider,
    "anthropic": AnthropicProvider,
}


def resolve_provider(
    name: str,
    client: httpx.AsyncClient,
    upstream_api_key: str,
) -> BaseProvider:
    provider_cls = PROVIDERS.get(name.lower())
    if provider_cls is None:
        supported = ", ".join(sorted(PROVIDERS))
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported provider: {name}. Supported: {supported}",
        )
    return provider_cls(client=client, upstream_api_key=upstream_api_key)
