import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import AsyncGenerator, Optional

import httpx
from fastapi import HTTPException, Request
from pydantic import SecretStr

from app.core.cache import build_cache_key, get_cached_response, set_cached_response
from app.core.budgets import BudgetExceeded, reserve_team_budget
from app.core.usage import set_request_usage, usage_from_response
from app.models.chat import ChatCompletionBody, ChatCompletionResponse, GatewayChatRequest
from app.providers.base import BaseProvider
from app.providers.registry import resolve_provider


@dataclass
class FallbackConfig:
    gateway_request: GatewayChatRequest
    alternatives: list[GatewayChatRequest] = field(default_factory=list)

    @property
    def candidates(self) -> list[GatewayChatRequest]:
        return [self.gateway_request, *self.alternatives]


async def _reserve_budget(
    request: Request,
    gateway_request: GatewayChatRequest,
    fallback: Optional[FallbackConfig],
) -> None:
    api_key = getattr(request.state, "api_key", None)
    if api_key is None:
        return
    fallback_models = [candidate.model for candidate in fallback.candidates] if fallback else []
    try:
        reservation_id, reservation_amount = await reserve_team_budget(
            api_key_id=api_key.id,
            team_id=getattr(api_key, "team_id", None),
            gateway_request=gateway_request,
            fallback_models=fallback_models,
        )
    except BudgetExceeded as exc:
        now = datetime.now(timezone.utc)
        next_month = (
            datetime(now.year + 1, 1, 1, tzinfo=timezone.utc)
            if now.month == 12
            else datetime(now.year, now.month + 1, 1, tzinfo=timezone.utc)
        )
        retry_after = max(1, int((next_month - now).total_seconds()))
        raise HTTPException(
            status_code=429,
            detail={
                "code": "monthly_budget_exceeded",
                "message": "The team's monthly estimated-spend limit would be exceeded.",
                "limitUsd": str(exc.limit),
                "spentUsd": str(exc.spent),
                "reservedUsd": str(exc.reserved),
                "requestedUsd": str(exc.requested),
                "period": "UTC calendar month",
            },
            headers={"Retry-After": str(retry_after)},
        )
    request.state.budget_reservation_id = reservation_id
    request.state.budget_reservation_amount = reservation_amount


def _set_completion_usage(request: Request, gateway_request: GatewayChatRequest, response: ChatCompletionResponse) -> None:
    usage = usage_from_response(response)
    set_request_usage(request.state, model=gateway_request.model, usage=usage)
    request.state.provider = gateway_request.provider
    request.state.model = gateway_request.model
    if (
        usage["prompt_tokens"] == 0
        and usage["completion_tokens"] == 0
        and getattr(request.state, "budget_reservation_amount", None) is not None
    ):
        request.state.cost_usd = float(request.state.budget_reservation_amount)


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
    policy_fallbacks = list(getattr(request.state, "policy_route_fallbacks", []))
    if not provider or not api_key:
        if not policy_fallbacks:
            return None
        return FallbackConfig(
            gateway_request=policy_fallbacks[0],
            alternatives=policy_fallbacks[1:],
        )
    explicit_fallback = body.to_fallback_gateway(
        provider=provider,
        api_key=SecretStr(api_key),
    )
    return FallbackConfig(
        gateway_request=explicit_fallback,
        alternatives=policy_fallbacks,
    )


def _should_fallback(exc: Exception) -> bool:
    if isinstance(exc, httpx.TimeoutException):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code >= 500
    return False


import asyncio

async def _complete_with_provider(
    provider: BaseProvider, gateway_request: GatewayChatRequest
) -> ChatCompletionResponse:
    retries = gateway_request.max_retries if gateway_request.max_retries is not None else 2
    for attempt in range(retries + 1):
        try:
            return await provider.complete(gateway_request)
        except Exception as exc:
            if attempt < retries and (isinstance(exc, httpx.TimeoutException) or (isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code == 429)):
                await asyncio.sleep(2 ** attempt)
                continue
            raise


async def execute_completion(
    request: Request,
    body: ChatCompletionBody,
    gateway_request: GatewayChatRequest,
    fallback: Optional[FallbackConfig],
) -> ChatCompletionResponse:
    api_key = getattr(request.state, "api_key", None)
    cache_bypassed = "no-cache" in request.headers.get("cache-control", "").lower()
    cache_key = None
    if api_key and not gateway_request.stream and not cache_bypassed:
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
            request.state.cost_usd = 0.0
            return response

    await _reserve_budget(request, gateway_request, fallback)

    provider = resolve_provider(
        gateway_request.provider,
        request.app.state.http_client,
        gateway_request.api_key.get_secret_value(),
    )

    effective_request = gateway_request
    try:
        response = await _complete_with_provider(provider, gateway_request)
    except Exception as exc:
        last_error = exc
        response = None
        if fallback and _should_fallback(exc):
            request.state.fallback_used = True
            for fallback_request in fallback.candidates:
                fb_provider = resolve_provider(
                    fallback_request.provider,
                    request.app.state.http_client,
                    fallback_request.api_key.get_secret_value(),
                )
                try:
                    response = await _complete_with_provider(fb_provider, fallback_request)
                    effective_request = fallback_request
                    break
                except Exception as fallback_error:
                    last_error = fallback_error
                    if not _should_fallback(fallback_error):
                        break
        if response is None and isinstance(last_error, httpx.HTTPStatusError):
            raise HTTPException(
                status_code=last_error.response.status_code,
                detail="Upstream provider error",
            ) from last_error
        elif response is None and isinstance(last_error, httpx.TimeoutException):
            raise HTTPException(
                status_code=504,
                detail="Upstream provider timed out",
            ) from last_error
        elif response is None:
            raise last_error

    _set_completion_usage(request, effective_request, response)

    if cache_key and not cache_bypassed:
        await set_cached_response(cache_key, response.model_dump(mode="json"))

    return response


async def execute_stream(
    request: Request,
    gateway_request: GatewayChatRequest,
    fallback: Optional[FallbackConfig],
    *,
    budget_reserved: bool = False,
) -> AsyncGenerator[str, None]:
    if not budget_reserved:
        await _reserve_budget(request, gateway_request, fallback)
    provider = resolve_provider(
        gateway_request.provider,
        request.app.state.http_client,
        gateway_request.api_key.get_secret_value(),
    )

    async def _stream_from(prov: BaseProvider, req: GatewayChatRequest) -> AsyncGenerator[str, None]:
        chars_yielded = 0
        request.state.prompt_tokens = 0
        request.state.completion_tokens = 0
        request.state.total_tokens = 0
        request.state.cost_usd = 0.0
        request.state.provider = req.provider
        request.state.model = req.model
        async for chunk in prov.stream(req):
            if chunk.startswith("data: ") and chunk != "data: [DONE]\n\n":
                try:
                    data = json.loads(chunk[6:])
                    
                    if "choices" in data and data["choices"]:
                        delta = data["choices"][0].get("delta", {})
                        chars_yielded += len(delta.get("content", ""))
                    
                    if "usage" in data and data["usage"]:
                        usage = data["usage"]
                        request.state.prompt_tokens = usage.get("prompt_tokens", 0)
                        request.state.completion_tokens = usage.get("completion_tokens", 0)
                        request.state.total_tokens = usage.get("total_tokens", 0)
                except json.JSONDecodeError:
                    pass
            elif chunk == "data: [DONE]\n\n":
                if not getattr(request.state, "total_tokens", 0):
                    comp_tokens = max(1, chars_yielded // 4)
                    request.state.completion_tokens = comp_tokens
                    request.state.prompt_tokens = max(
                        1,
                        sum(len(message.content.encode("utf-8")) for message in req.messages),
                    )
                    request.state.total_tokens = request.state.prompt_tokens + comp_tokens
                    set_request_usage(
                        request.state,
                        model=req.model,
                        usage={
                            "prompt_tokens": request.state.prompt_tokens,
                            "completion_tokens": comp_tokens,
                            "total_tokens": request.state.total_tokens,
                        },
                    )
                if (
                    getattr(request.state, "total_tokens", 0) == 0
                    and getattr(request.state, "budget_reservation_amount", None) is not None
                ):
                    request.state.cost_usd = float(request.state.budget_reservation_amount)
            yield chunk

    try:
        async for chunk in _stream_from(provider, gateway_request):
            yield chunk
    except Exception as exc:
        if fallback and _should_fallback(exc):
            request.state.fallback_used = True
            last_error = exc
            for fallback_request in fallback.candidates:
                fb_provider = resolve_provider(
                    fallback_request.provider,
                    request.app.state.http_client,
                    fallback_request.api_key.get_secret_value(),
                )
                try:
                    async for chunk in _stream_from(fb_provider, fallback_request):
                        yield chunk
                    return
                except Exception as fb_exc:
                    last_error = fb_exc
                    if not _should_fallback(fb_exc):
                        break
            err_msg = str(last_error).replace('"', '\\"')
            yield f'data: {{"error": "Fallback failed: {err_msg}"}}\n\n'
        elif isinstance(exc, httpx.HTTPStatusError):
            try:
                detail = exc.response.json().get('error', {}).get('message', 'Upstream provider error')
            except Exception:
                detail = f"Upstream HTTP {exc.response.status_code} Error"
            detail = detail.replace('"', '\\"')
            yield f'data: {{"error": "{detail}"}}\n\n'
        elif isinstance(exc, httpx.TimeoutException):
            yield 'data: {"error": "Upstream provider timed out"}\n\n'
        else:
            err_msg = str(exc).replace('"', '\\"')
            yield f'data: {{"error": "Internal Error: {err_msg}"}}\n\n'
