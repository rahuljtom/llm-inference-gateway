from typing import AsyncGenerator

import httpx

from app.core.settings import settings
from app.models.chat import ChatCompletionResponse, GatewayChatRequest
from app.providers.base import BaseProvider

_REQUEST_TIMEOUT = httpx.Timeout(settings.PROVIDER_TIMEOUT_SECONDS)


class OpenAICompatibleProvider(BaseProvider):
    """Shared adapter for OpenAI-compatible chat/completions endpoints."""

    def __init__(
        self,
        client: httpx.AsyncClient,
        upstream_api_key: str,
        api_url: str,
    ):
        super().__init__(client, upstream_api_key)
        self.api_url = api_url

    def _headers(self):
        headers = {
            "Content-Type": "application/json",
        }
        if self.upstream_api_key:
            headers["Authorization"] = f"Bearer {self.upstream_api_key}"
        return headers

    async def complete(self, request: GatewayChatRequest) -> ChatCompletionResponse:
        payload = request.upstream_payload()
        response = await self.client.post(
            self.api_url,
            headers=self._headers(),
            json=payload,
            timeout=_REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        return ChatCompletionResponse(**response.json())

    async def stream(self, request: GatewayChatRequest) -> AsyncGenerator[str, None]:
        payload = request.upstream_payload()
        payload["stream"] = True
        payload["stream_options"] = {"include_usage": True}

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
                    if line == "data: [DONE]":
                        yield "data: [DONE]\n\n"
                        break
                    yield f"{line}\n\n"
