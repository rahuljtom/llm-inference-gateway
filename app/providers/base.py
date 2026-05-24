from abc import ABC, abstractmethod
from typing import AsyncGenerator

import httpx

from app.models.chat import ChatCompletionResponse, GatewayChatRequest


class BaseProvider(ABC):
    """
    Abstract base class for all LLM providers (OpenAI, Anthropic, Groq).
    Enforces a strict interface for generating standard responses and SSE streams.
    """

    def __init__(self, client: httpx.AsyncClient, upstream_api_key: str):
        self.client = client
        self.upstream_api_key = upstream_api_key

    @abstractmethod
    async def complete(self, request: GatewayChatRequest) -> ChatCompletionResponse:
        """Handles non-streaming requests and returns a normalized response."""
        pass

    @abstractmethod
    async def stream(self, request: GatewayChatRequest) -> AsyncGenerator[str, None]:
        """
        Handles streaming requests and yields SSE formatted strings:
        data: {"id": "...", "choices": [{"delta": {"content": "..."}}]}
        """
        pass
