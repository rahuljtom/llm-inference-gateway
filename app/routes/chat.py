from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from app.models.chat import ChatCompletionBody
from app.services.inference import (
    _resolve_fallback,
    execute_completion,
    execute_stream,
)
from app.services.ingress import build_gateway_request

router = APIRouter(prefix="/v1", tags=["chat"])


@router.post("/chat/completions")
async def chat_completions(body: ChatCompletionBody, request: Request):
    gateway_request = build_gateway_request(request, body)
    fallback = _resolve_fallback(request, body)

    request.state.provider = gateway_request.provider
    request.state.model = gateway_request.model
    request.state.cached = False
    request.state.fallback_used = False

    if gateway_request.stream:
        return StreamingResponse(
            execute_stream(request, gateway_request, fallback),
            media_type="text/event-stream",
        )

    return await execute_completion(request, body, gateway_request, fallback)
