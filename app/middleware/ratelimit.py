import json

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.core.rate_limiter import check_rate_limit, check_tpm_rate_limit, record_tpm_usage
EXEMPT_PATHS = frozenset({"/health", "/docs", "/openapi.json", "/redoc", "/admin", "/admin/api/stats"})
CHAT_PATH = "/v1/chat/completions"
_CHARS_PER_TOKEN = 4
_DEFAULT_COMPLETION_RESERVE = 1024


def _estimate_tokens_from_json(body: dict) -> int:
    messages = body.get("messages") or []
    chars = sum(len(m.get("content", "")) for m in messages if isinstance(m, dict))
    prompt = max(1, chars // _CHARS_PER_TOKEN)
    completion = body.get("max_tokens") or _DEFAULT_COMPLETION_RESERVE
    return prompt + completion


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Enforces per-API-key RPM and TPM limits.
    TPM uses a pre-request estimate; actual usage is recorded after the response.
    """

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

        rpm_result = await check_rate_limit(
            key=f"api:{api_key.id}:rpm",
            limit=api_key.rpm_limit,
            window_seconds=60,
        )
        if not rpm_result.allowed:
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded (requests per minute)."},
                headers={
                    "Retry-After": str(rpm_result.retry_after),
                    "X-RateLimit-Limit": str(rpm_result.limit),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Type": "rpm",
                },
            )

        token_estimate = 0
        if request.url.path == CHAT_PATH:
            try:
                body = json.loads(await request.body())
                token_estimate = _estimate_tokens_from_json(body)
            except (json.JSONDecodeError, UnicodeDecodeError):
                token_estimate = _DEFAULT_COMPLETION_RESERVE

            tpm_result = await check_tpm_rate_limit(
                key=f"api:{api_key.id}:tpm",
                token_estimate=token_estimate,
                limit=api_key.tpm_limit,
                window_seconds=60,
            )
            if not tpm_result.allowed:
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Rate limit exceeded (tokens per minute)."},
                    headers={
                        "Retry-After": str(tpm_result.retry_after),
                        "X-RateLimit-Limit": str(tpm_result.limit),
                        "X-RateLimit-Remaining": "0",
                        "X-RateLimit-Type": "tpm",
                    },
                )

        response = await call_next(request)

        actual_tokens = getattr(request.state, "total_tokens", 0)
        if actual_tokens > 0:
            await record_tpm_usage(f"api:{api_key.id}:tpm", actual_tokens)

        response.headers["X-RateLimit-Limit-RPM"] = str(rpm_result.limit)
        response.headers["X-RateLimit-Remaining-RPM"] = str(rpm_result.remaining)
        if request.url.path == CHAT_PATH:
            response.headers["X-RateLimit-Limit-TPM"] = str(api_key.tpm_limit)

        return response
