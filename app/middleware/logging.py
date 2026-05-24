"""
Request logging middleware.

Captures provider, model, latency, and token counts for every proxied request
and writes them asynchronously to Postgres. Provider/model are set on
request.state by the chat route (never read from the request body here).
"""

import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from sqlmodel.ext.asyncio.session import AsyncSession

from app.db.session import engine
from app.models.db import RequestLog

EXEMPT_PATHS = frozenset({"/health", "/docs", "/openapi.json", "/redoc"})


class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path in EXEMPT_PATHS:
            return await call_next(request)

        api_key = getattr(request.state, "api_key", None)
        if api_key is None:
            return await call_next(request)

        start = time.perf_counter()
        response = await call_next(request)
        latency_ms = int((time.perf_counter() - start) * 1000)

        provider = getattr(request.state, "provider", "unknown")
        model = getattr(request.state, "model", "unknown")

        prompt_tokens = int(response.headers.get("x-prompt-tokens", 0))
        completion_tokens = int(response.headers.get("x-completion-tokens", 0))

        try:
            async with AsyncSession(engine) as session:
                log = RequestLog(
                    api_key_id=api_key.id,
                    provider=provider,
                    model=model,
                    latency_ms=latency_ms,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=prompt_tokens + completion_tokens,
                )
                session.add(log)
                await session.commit()
        except Exception:
            pass

        return response
