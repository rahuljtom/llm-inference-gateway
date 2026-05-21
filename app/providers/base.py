from abc import ABC, abstractmethod
from typing import AsyncGenerator
from app.models.chat import ChatCompletionRequest, ChatCompletionResponse

class BaseProvider(ABC):
    """
    Abstract base class for all LLM providers (OpenAI, Anthropic, Groq).
    Enforces a strict interface for generating standard responses and SSE streams.
    """
    
    @abstractmethod
    async def complete(self, request: ChatCompletionRequest) -> ChatCompletionResponse:
        """Handles non-streaming requests and returns a normalized response."""
        pass

    @abstractmethod
    async def stream(self, request: ChatCompletionRequest) -> AsyncGenerator[str, None]:
        """
        Handles streaming requests and yields SSE formatted strings:
        data: {"id": "...", "choices": [{"delta": {"content": "..."}}]}
        """
        pass
