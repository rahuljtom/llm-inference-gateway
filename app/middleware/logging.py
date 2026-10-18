"""
Request logging middleware.

Writes provider, model, latency, tokens, cost, cache, and fallback flags to Postgres.
"""

import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from sqlmodel.ext.asyncio.session import AsyncSession

from app.db.session import engine
from app.core.budgets import finalize_budget_reservation
from app.core.pricing import estimate_cost_usd
from app.models.db import RequestLog

EXEMPT_PATHS = frozenset({
    "/health",
    "/docs",
    "/openapi.json",
    "/redoc",
})


class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if (
            path in EXEMPT_PATHS
            or path == "/"
            or path == "/favicon.ico"
            or path.startswith("/static")
            or path.startswith("/assets")
            or path.startswith("/admin/api")
        ):
            return await call_next(request)

        api_key = getattr(request.state, "api_key", None)
        if api_key is None:
            return await call_next(request)

        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            await self._persist_request(request, start, None)
            raise

        if hasattr(response, "body_iterator"):
            original_iterator = response.body_iterator

            async def persist_after_stream():
                try:
                    async for chunk in original_iterator:
                        yield chunk
                finally:
                    await self._persist_request(request, start, response)

            response.body_iterator = persist_after_stream()
            return response

        await self._persist_request(request, start, response)
        return response

    async def _persist_request(self, request: Request, start: float, response) -> None:
        latency_ms = int((time.perf_counter() - start) * 1000)
        api_key = getattr(request.state, "api_key", None)
        if api_key is None:
            return

        provider = getattr(request.state, "provider", "unknown")
        model = getattr(request.state, "model", "unknown")
        prompt_tokens = getattr(request.state, "prompt_tokens", 0)
        completion_tokens = getattr(request.state, "completion_tokens", 0)
        total_tokens = getattr(request.state, "total_tokens", prompt_tokens + completion_tokens)
        cost_usd = getattr(request.state, "cost_usd", 0.0)
        cached = getattr(request.state, "cached", False)
        reservation_id = getattr(request.state, "budget_reservation_id", None)
        reservation_amount = getattr(request.state, "budget_reservation_amount", None)
        if reservation_id and response is not None and response.status_code < 400 and cost_usd <= 0:
            cost_usd = float(reservation_amount or 0)
        if cost_usd <= 0 and (prompt_tokens or completion_tokens) and not cached:
            cost_usd = estimate_cost_usd(model, prompt_tokens, completion_tokens)
        fallback_used = getattr(request.state, "fallback_used", False)

        try:
            async with AsyncSession(engine) as session:
                log = RequestLog(
                    api_key_id=api_key.id,
                    provider=provider,
                    model=model,
                    latency_ms=latency_ms,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=total_tokens,
                    cost_usd=cost_usd,
                    cached=cached,
                    fallback_used=fallback_used,
                )
                session.add(log)
                await finalize_budget_reservation(
                    session,
                    reservation_id,
                    getattr(api_key, "team_id", None),
                    cost_usd,
                )
                await session.commit()
        except Exception:
            pass
