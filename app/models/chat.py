from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, SecretStr, field_validator

ProviderName = Literal["openai", "groq", "anthropic"]


class ChatMessage(BaseModel):
    role: str
    content: str


class GatewayChatRequest(BaseModel):
    """Inbound gateway request: BYOK provider credentials + OpenAI-shaped payload."""

    provider: str
    api_key: SecretStr
    model: str
    messages: List[ChatMessage]
    temperature: Optional[float] = Field(default=1.0, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(default=None, ge=1)
    stream: Optional[bool] = False

    @field_validator("provider")
    @classmethod
    def normalize_provider(cls, value: str) -> str:
        return value.strip().lower()

    def upstream_payload(self) -> Dict[str, Any]:
        return self.model_dump(
            exclude={"provider", "api_key"},
            exclude_none=True,
            mode="json",
        )


# Backwards-compatible alias for provider adapters
ChatCompletionRequest = GatewayChatRequest


class Choice(BaseModel):
    index: int
    message: ChatMessage
    finish_reason: Optional[str] = None


class ChatCompletionResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: List[Choice]
    usage: Optional[Dict[str, Any]] = None
