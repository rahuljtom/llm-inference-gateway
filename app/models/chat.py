from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, SecretStr, field_validator

ProviderName = Literal["openai", "groq", "anthropic"]


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatCompletionBody(BaseModel):
    """
    Inbound JSON body: OpenAI-shaped fields with optional BYOK credentials.
    Credentials may also be supplied via X-Provider / X-Provider-Api-Key headers.
    """

    provider: Optional[str] = None
    api_key: Optional[SecretStr] = None
    model: str
    messages: List[ChatMessage]
    temperature: Optional[float] = Field(default=1.0, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(default=None, ge=1)
    stream: Optional[bool] = False

    @field_validator("provider")
    @classmethod
    def normalize_provider(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        return value.strip().lower()

    def to_gateway(self, provider: str, api_key: SecretStr) -> "GatewayChatRequest":
        return GatewayChatRequest(
            provider=provider,
            api_key=api_key,
            model=self.model,
            messages=self.messages,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            stream=self.stream,
        )


class GatewayChatRequest(BaseModel):
    """Internal request passed to provider adapters (credentials always resolved)."""

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
