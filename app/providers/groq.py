import json
from typing import AsyncGenerator
import httpx

from app.models.chat import ChatCompletionRequest, ChatCompletionResponse
from app.providers.base import BaseProvider
from app.core.settings import settings

class GroqProvider(BaseProvider):
    def __init__(self, client: httpx.AsyncClient):
        self.client = client
        self.api_url = "https://api.groq.com/openai/v1/chat/completions"
        self.headers = {
            "Authorization": f"Bearer {settings.GROQ_API_KEY}",
            "Content-Type": "application/json"
        }

    async def complete(self, request: ChatCompletionRequest) -> ChatCompletionResponse:
        payload = request.model_dump(exclude_none=True)
        response = await self.client.post(self.api_url, headers=self.headers, json=payload)
        response.raise_for_status()
        
        # Groq natively uses the OpenAI schema, so we can drop it straight in
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
                    # Forward exact SSE chunks as Groq is OpenAI-compatible
                    yield f"{line}\n\n"
