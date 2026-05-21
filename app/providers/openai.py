import json
from typing import AsyncGenerator
import httpx

from app.models.chat import ChatCompletionRequest, ChatCompletionResponse
from app.providers.base import BaseProvider
from app.core.settings import settings

class OpenAIProvider(BaseProvider):
    def __init__(self, client: httpx.AsyncClient):
        self.client = client
        self.api_url = "https://api.openai.com/v1/chat/completions"
        self.headers = {
            "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
            "Content-Type": "application/json"
        }

    async def complete(self, request: ChatCompletionRequest) -> ChatCompletionResponse:
        payload = request.model_dump(exclude_none=True)
        response = await self.client.post(self.api_url, headers=self.headers, json=payload)
        response.raise_for_status()
        
        # OpenAI natively returns a schema that matches our ChatCompletionResponse
        return ChatCompletionResponse(**response.json())

    async def stream(self, request: ChatCompletionRequest) -> AsyncGenerator[str, None]:
        payload = request.model_dump(exclude_none=True)
        payload["stream"] = True
        
        async with self.client.stream("POST", self.api_url, headers=self.headers, json=payload) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    if line == "data: [DONE]":
                        yield "data: [DONE]\n\n"
                        break
                    # Forward exact OpenAI SSE chunks as our normalized response
                    yield f"{line}\n\n"
