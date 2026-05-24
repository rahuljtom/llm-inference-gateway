from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from app.models.chat import ChatCompletionBody
from app.providers.registry import resolve_provider
from app.services.ingress import build_gateway_request

router = APIRouter(prefix="/v1", tags=["chat"])


@router.post("/chat/completions")
async def chat_completions(body: ChatCompletionBody, request: Request):
    gateway_request = build_gateway_request(request, body)

    request.state.provider = gateway_request.provider
    request.state.model = gateway_request.model

    provider = resolve_provider(
        gateway_request.provider,
        request.app.state.http_client,
        gateway_request.api_key.get_secret_value(),
    )

    if gateway_request.stream:
        return StreamingResponse(
            provider.stream(gateway_request),
            media_type="text/event-stream",
        )

    return await provider.complete(gateway_request)
