from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from app.models.chat import GatewayChatRequest
from app.providers.registry import resolve_provider

router = APIRouter(prefix="/v1", tags=["chat"])


@router.post("/chat/completions")
async def chat_completions(body: GatewayChatRequest, request: Request):
    request.state.provider = body.provider
    request.state.model = body.model

    provider = resolve_provider(
        body.provider,
        request.app.state.http_client,
        body.api_key.get_secret_value(),
    )

    if body.stream:
        return StreamingResponse(
            provider.stream(body),
            media_type="text/event-stream",
        )

    return await provider.complete(body)
