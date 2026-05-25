from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.core.security import hash_api_key
from app.db.session import get_api_key_by_hash

EXEMPT_PATHS = frozenset({
    "/health",
    "/docs",
    "/openapi.json",
    "/redoc",
    "/admin",
    "/admin/api/stats",
})


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if (
            path in EXEMPT_PATHS
            or path == "/"
            or path == "/favicon.ico"
            or path.startswith("/static")
        ):
            return await call_next(request)

        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return JSONResponse(
                status_code=401,
                content={"detail": "Missing or invalid API key"},
            )

        raw_key = auth_header.removeprefix("Bearer ").strip()
        if not raw_key:
            return JSONResponse(
                status_code=401,
                content={"detail": "Missing or invalid API key"},
            )

        api_key = await get_api_key_by_hash(hash_api_key(raw_key))
        if api_key is None:
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid API key"},
            )

        request.state.api_key = api_key
        return await call_next(request)
