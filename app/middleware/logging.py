"""
Request logging middleware.

Writes provider, model, latency, tokens, cost, cache, and fallback flags to Postgres.
"""

import time

import anyio
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


class LoggingMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive=receive)
        path = scope["path"]
        if (
            path in EXEMPT_PATHS
            or path == "/"
            or path == "/favicon.ico"
            or path.startswith("/static")
            or path.startswith("/assets")
            or path.startswith("/admin/api")
        ):
            await self.app(scope, receive, send)
            return

        api_key = getattr(request.state, "api_key", None)
        if api_key is None:
            await self.app(scope, receive, send)
            return

        start = time.perf_counter()
        response_status = None
        persisted = False

        async def persist_once():
            nonlocal persisted
            if not persisted:
                persisted = True
                with anyio.CancelScope(shield=True):
                    await self._persist_request(request, start, response_status)

        async def send_with_logging(message):
            nonlocal response_status
            if message["type"] == "http.response.start":
                response_status = message["status"]
            await send(message)
            if message["type"] == "http.response.body" and not message.get("more_body", False):
                await persist_once()

        try:
            await self.app(scope, receive, send_with_logging)
        except BaseException:
            await persist_once()
            raise
        await persist_once()

    async def _persist_request(self, request: Request, start: float, response_status: int | None) -> None:
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
        if reservation_id and response_status is not None and response_status < 400 and cost_usd <= 0:
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
