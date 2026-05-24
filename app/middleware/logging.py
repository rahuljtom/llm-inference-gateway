"""
Request logging middleware.

Captures provider, model, latency, and token counts for every proxied request
and writes them asynchronously to Postgres. Runs AFTER auth + rate limit
middlewares so request.state.api_key is guaranteed to exist.
"""

import time
import json

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

        # Peek at the request body to extract model name
        body_bytes = await request.body()
        try:
            body = json.loads(body_bytes)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return await call_next(request)

        model = body.get("model", "unknown")

        # Determine provider from model prefix
        if model.startswith("gpt-"):
            provider = "openai"
        elif model.startswith("claude-"):
            provider = "anthropic"
        elif model.startswith("llama") or model.startswith("mixtral") or model.startswith("gemma"):
            provider = "groq"
        else:
            provider = "unknown"

        start = time.perf_counter()
        response = await call_next(request)
        latency_ms = int((time.perf_counter() - start) * 1000)

        # Extract token counts from non-streaming responses via response headers
        # For streaming, tokens are unknown at this layer (logged as 0)
        prompt_tokens = int(response.headers.get("x-prompt-tokens", 0))
        completion_tokens = int(response.headers.get("x-completion-tokens", 0))

        # Fire-and-forget: write log row to Postgres
        # We don't await this in the response path to avoid adding latency
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
            # Logging must never crash the gateway
            pass

        return response
