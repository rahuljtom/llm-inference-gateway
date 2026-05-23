import json
import time
from typing import AsyncGenerator
import httpx

from app.models.chat import ChatCompletionRequest, ChatCompletionResponse, Choice, ChatMessage
from app.providers.base import BaseProvider
from app.core.settings import settings

class AnthropicProvider(BaseProvider):
    def __init__(self, client: httpx.AsyncClient):
        self.client = client
        self.api_url = "https://api.anthropic.com/v1/messages"
        self.headers = {
            "x-api-key": settings.ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }

    async def complete(self, request: ChatCompletionRequest) -> ChatCompletionResponse:
        anthropic_messages = [{"role": m.role, "content": m.content} for m in request.messages if m.role != "system"]
        system_message = next((m.content for m in request.messages if m.role == "system"), "")
        
        payload = {
            "model": request.model,
            "max_tokens": request.max_tokens or 1024,
            "messages": anthropic_messages,
            "temperature": request.temperature,
        }
        if system_message:
            payload["system"] = system_message

        response = await self.client.post(self.api_url, headers=self.headers, json=payload)
        response.raise_for_status()
        data = response.json()

        return ChatCompletionResponse(
            id=data.get("id", f"ant-{int(time.time())}"),
            created=int(time.time()),
            model=request.model,
            choices=[
                Choice(
                    index=0,
                    message=ChatMessage(role="assistant", content=data["content"][0]["text"]),
                    finish_reason="stop"
                )
            ]
        )

    async def stream(self, request: ChatCompletionRequest) -> AsyncGenerator[str, None]:
        anthropic_messages = [{"role": m.role, "content": m.content} for m in request.messages if m.role != "system"]
        system_message = next((m.content for m in request.messages if m.role == "system"), "")
        
        payload = {
            "model": request.model,
            "max_tokens": request.max_tokens or 1024,
            "messages": anthropic_messages,
            "temperature": request.temperature,
            "stream": True
        }
        if system_message:
            payload["system"] = system_message

        async with self.client.stream("POST", self.api_url, headers=self.headers, json=payload) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data_str = line[6:]
                    if data_str == "[DONE]":
                        yield "data: [DONE]\n\n"
                        break
                    
                    try:
                        chunk = json.loads(data_str)
                        if chunk.get("type") == "content_block_delta" and chunk["delta"]["type"] == "text_delta":
                            out = {
                                "id": f"ant-chunk-{int(time.time())}",
                                "choices": [{"delta": {"content": chunk["delta"]["text"]}}]
                            }
                            yield f"data: {json.dumps(out)}\n\n"
                    except json.JSONDecodeError:
                        continue
