"""
Request logging middleware.

Writes provider, model, latency, tokens, cost, cache, and fallback flags to Postgres.
"""

import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from sqlmodel.ext.asyncio.session import AsyncSession

from app.db.session import engine
from app.models.db import RequestLog

EXEMPT_PATHS = frozenset({
    "/health",
    "/docs",
    "/openapi.json",
    "/redoc",
    "/admin",
    "/admin/api/stats",
})


class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if (
            path in EXEMPT_PATHS
            or path == "/"
            or path == "/favicon.ico"
            or path.startswith("/static")
        ):
            return await call_next(request)

        api_key = getattr(request.state, "api_key", None)
        if api_key is None:
            return await call_next(request)

        start = time.perf_counter()
        response = await call_next(request)
        latency_ms = int((time.perf_counter() - start) * 1000)

        provider = getattr(request.state, "provider", "unknown")
        model = getattr(request.state, "model", "unknown")
        prompt_tokens = getattr(request.state, "prompt_tokens", 0)
        completion_tokens = getattr(request.state, "completion_tokens", 0)
        total_tokens = getattr(request.state, "total_tokens", prompt_tokens + completion_tokens)
        cost_usd = getattr(request.state, "cost_usd", 0.0)
        cached = getattr(request.state, "cached", False)
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
                await session.commit()
        except Exception:
            pass

        return response
