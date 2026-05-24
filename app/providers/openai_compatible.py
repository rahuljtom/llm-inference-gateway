from typing import AsyncGenerator

import httpx

from app.models.chat import ChatCompletionResponse, GatewayChatRequest
from app.providers.base import BaseProvider


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
        return {
            "Authorization": f"Bearer {self.upstream_api_key}",
            "Content-Type": "application/json",
        }

    async def complete(self, request: GatewayChatRequest) -> ChatCompletionResponse:
        payload = request.upstream_payload()
        response = await self.client.post(
            self.api_url, headers=self._headers(), json=payload
        )
        response.raise_for_status()
        return ChatCompletionResponse(**response.json())

    async def stream(self, request: GatewayChatRequest) -> AsyncGenerator[str, None]:
        payload = request.upstream_payload()
        payload["stream"] = True

        async with self.client.stream(
            "POST", self.api_url, headers=self._headers(), json=payload
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    if line == "data: [DONE]":
                        yield "data: [DONE]\n\n"
                        break
                    yield f"{line}\n\n"
