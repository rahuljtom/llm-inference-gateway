import json
import time
from typing import AsyncGenerator

import httpx

from app.core.settings import settings
from app.models.chat import (
    ChatCompletionResponse,
    ChatMessage,
    Choice,
    GatewayChatRequest,
)
from app.providers.base import BaseProvider

ANTHROPIC_MESSAGES_URL = "https://api.anthropic.com/v1/messages"
_REQUEST_TIMEOUT = httpx.Timeout(settings.PROVIDER_TIMEOUT_SECONDS)


class AnthropicProvider(BaseProvider):
    def __init__(self, client: httpx.AsyncClient, upstream_api_key: str):
        super().__init__(client, upstream_api_key)
        self.api_url = ANTHROPIC_MESSAGES_URL

    def _headers(self) -> dict:
        return {
            "x-api-key": self.upstream_api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

    def _anthropic_payload(self, request: GatewayChatRequest, stream: bool = False) -> dict:
        anthropic_messages = [
            {"role": m.role, "content": m.content}
            for m in request.messages
            if m.role != "system"
        ]
        system_message = next(
            (m.content for m in request.messages if m.role == "system"), ""
        )

        payload = {
            "model": request.model,
            "max_tokens": request.max_tokens or 1024,
            "messages": anthropic_messages,
            "temperature": request.temperature,
        }
        if system_message:
            payload["system"] = system_message
        if stream:
            payload["stream"] = True
        return payload

    async def complete(self, request: GatewayChatRequest) -> ChatCompletionResponse:
        payload = self._anthropic_payload(request)
        response = await self.client.post(
            self.api_url,
            headers=self._headers(),
            json=payload,
            timeout=_REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        data = response.json()
        usage_data = data.get("usage") or {}
        input_tokens = usage_data.get("input_tokens", 0)
        output_tokens = usage_data.get("output_tokens", 0)

        return ChatCompletionResponse(
            id=data.get("id", f"ant-{int(time.time())}"),
            created=int(time.time()),
            model=request.model,
            choices=[
                Choice(
                    index=0,
                    message=ChatMessage(
                        role="assistant", content=data["content"][0]["text"]
                    ),
                    finish_reason="stop",
                )
            ],
            usage={
                "prompt_tokens": input_tokens,
                "completion_tokens": output_tokens,
                "total_tokens": input_tokens + output_tokens,
            },
        )

    async def stream(self, request: GatewayChatRequest) -> AsyncGenerator[str, None]:
        payload = self._anthropic_payload(request, stream=True)

        async with self.client.stream(
            "POST",
            self.api_url,
            headers=self._headers(),
            json=payload,
            timeout=_REQUEST_TIMEOUT,
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data_str = line[6:]
                    if data_str == "[DONE]":
                        yield "data: [DONE]\n\n"
                        break

                    try:
                        chunk = json.loads(data_str)
                        if (
                            chunk.get("type") == "content_block_delta"
                            and chunk["delta"]["type"] == "text_delta"
                        ):
                            out = {
                                "id": f"ant-chunk-{int(time.time())}",
                                "choices": [
                                    {"delta": {"content": chunk["delta"]["text"]}}
                                ],
                            }
                            yield f"data: {json.dumps(out)}\n\n"
                    except json.JSONDecodeError:
                        continue
