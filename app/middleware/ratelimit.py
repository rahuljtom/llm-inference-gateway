from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.core.rate_limiter import check_rate_limit

EXEMPT_PATHS = frozenset({"/health", "/docs", "/openapi.json", "/redoc"})


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Enforces per-API-key RPM limits using the sliding-window rate limiter.
    Relies on AuthMiddleware running first to populate request.state.api_key.
    Returns 429 with Retry-After header when the limit is breached.
    """

    async def dispatch(self, request: Request, call_next):
        if request.url.path in EXEMPT_PATHS:
            return await call_next(request)

        # api_key is set by AuthMiddleware; if missing, skip rate limiting
        api_key = getattr(request.state, "api_key", None)
        if api_key is None:
            return await call_next(request)

        result = await check_rate_limit(
            key=f"api:{api_key.id}:rpm",
            limit=api_key.rpm_limit,
            window_seconds=60
        )

        if not result.allowed:
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded. Try again later."},
                headers={
                    "Retry-After": str(result.retry_after),
                    "X-RateLimit-Limit": str(result.limit),
                    "X-RateLimit-Remaining": "0",
                },
            )

        response = await call_next(request)

        # Attach rate limit headers to every successful response
        response.headers["X-RateLimit-Limit"] = str(result.limit)
        response.headers["X-RateLimit-Remaining"] = str(result.remaining)

        return response
