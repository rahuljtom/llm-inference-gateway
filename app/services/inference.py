from dataclasses import dataclass
from typing import AsyncGenerator, Optional

import httpx
from fastapi import HTTPException, Request
from pydantic import SecretStr

from app.core.cache import build_cache_key, get_cached_response, set_cached_response
from app.core.usage import set_request_usage, usage_from_response
from app.models.chat import ChatCompletionBody, ChatCompletionResponse, GatewayChatRequest
from app.providers.base import BaseProvider
from app.providers.registry import resolve_provider


@dataclass
class FallbackConfig:
    gateway_request: GatewayChatRequest


def _resolve_fallback(
    request: Request, body: ChatCompletionBody
) -> Optional[FallbackConfig]:
    header_provider = request.headers.get("x-fallback-provider")
    header_key = request.headers.get("x-fallback-api-key")

    provider = (header_provider or body.fallback_provider or "").strip().lower()
    body_fb_key = (
        body.fallback_api_key.get_secret_value().strip() if body.fallback_api_key else ""
    )
    api_key = (header_key or body_fb_key or "").strip()
    if not provider or not api_key:
        return None
    return FallbackConfig(
        gateway_request=body.to_fallback_gateway(
            provider=provider,
            api_key=SecretStr(api_key),
        )
    )


def _should_fallback(exc: Exception) -> bool:
    if isinstance(exc, httpx.TimeoutException):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code >= 500
    return False


async def _complete_with_provider(
    provider: BaseProvider, gateway_request: GatewayChatRequest
) -> ChatCompletionResponse:
    return await provider.complete(gateway_request)


async def execute_completion(
    request: Request,
    body: ChatCompletionBody,
    gateway_request: GatewayChatRequest,
    fallback: Optional[FallbackConfig],
) -> ChatCompletionResponse:
    api_key = getattr(request.state, "api_key", None)
    cache_key = None
    if api_key and not gateway_request.stream:
        cache_key = build_cache_key(
            api_key.id,
            gateway_request.provider,
            gateway_request.model,
            gateway_request.upstream_payload(),
        )
        cached = await get_cached_response(cache_key)
        if cached:
            request.state.cached = True
            response = ChatCompletionResponse(**cached)
            set_request_usage(request.state, model=gateway_request.model, usage=usage_from_response(response))
            return response

    provider = resolve_provider(
        gateway_request.provider,
        request.app.state.http_client,
        gateway_request.api_key.get_secret_value(),
    )

    try:
        response = await _complete_with_provider(provider, gateway_request)
    except Exception as exc:
        if fallback and _should_fallback(exc):
            request.state.fallback_used = True
            fb_provider = resolve_provider(
                fallback.gateway_request.provider,
                request.app.state.http_client,
                fallback.gateway_request.api_key.get_secret_value(),
            )
            response = await _complete_with_provider(fb_provider, fallback.gateway_request)
        elif isinstance(exc, httpx.HTTPStatusError):
            raise HTTPException(
                status_code=exc.response.status_code,
                detail="Upstream provider error",
            ) from exc
        elif isinstance(exc, httpx.TimeoutException):
            raise HTTPException(
                status_code=504,
                detail="Upstream provider timed out",
            ) from exc
        else:
            raise

    set_request_usage(
        request.state,
        model=gateway_request.model,
        usage=usage_from_response(response),
    )

    if cache_key:
        await set_cached_response(cache_key, response.model_dump(mode="json"))

    return response


async def execute_stream(
    request: Request,
    gateway_request: GatewayChatRequest,
    fallback: Optional[FallbackConfig],
) -> AsyncGenerator[str, None]:
    provider = resolve_provider(
        gateway_request.provider,
        request.app.state.http_client,
        gateway_request.api_key.get_secret_value(),
    )

    async def _stream_from(prov: BaseProvider, req: GatewayChatRequest) -> AsyncGenerator[str, None]:
        async for chunk in prov.stream(req):
            yield chunk

    try:
        async for chunk in _stream_from(provider, gateway_request):
            yield chunk
    except Exception as exc:
        if fallback and _should_fallback(exc):
            request.state.fallback_used = True
            fb_provider = resolve_provider(
                fallback.gateway_request.provider,
                request.app.state.http_client,
                fallback.gateway_request.api_key.get_secret_value(),
            )
            async for chunk in _stream_from(fb_provider, fallback.gateway_request):
                yield chunk
        elif isinstance(exc, httpx.HTTPStatusError):
            raise HTTPException(
                status_code=exc.response.status_code,
                detail="Upstream provider error",
            ) from exc
        elif isinstance(exc, httpx.TimeoutException):
            raise HTTPException(
                status_code=504,
                detail="Upstream provider timed out",
            ) from exc
        else:
            raise
