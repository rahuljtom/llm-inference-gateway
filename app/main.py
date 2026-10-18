from contextlib import asynccontextmanager
import asyncio

from fastapi import FastAPI
from fastapi.responses import JSONResponse
import httpx
from sqlalchemy import text

from app.core.redis import redis_client
from app.db.session import engine, init_db, seed_demo_api_key
from app.middleware.auth import AuthMiddleware
from app.middleware.ratelimit import RateLimitMiddleware
from app.middleware.logging import LoggingMiddleware
from app.routes import chat
@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await seed_demo_api_key()

    # Initialize shared HTTP client for all downstream provider requests
    # This prevents socket exhaustion under load
    app.state.http_client = httpx.AsyncClient(timeout=60.0)
    yield
    # Clean up gracefully on shutdown
    await app.state.http_client.aclose()
    await redis_client.aclose()
    await engine.dispose()

app = FastAPI(
    title="LLM Inference Gateway",
    description="Production-shaped OpenAI-compatible gateway",
    version="0.1.0",
    lifespan=lifespan
)

app.add_middleware(LoggingMiddleware)     # runs third: logs request to postgres
app.add_middleware(RateLimitMiddleware)   # runs second: checks limits
app.add_middleware(AuthMiddleware)        # runs first: populates api_key

from app.routes.chat import router as chat_router
from app.routes.admin import router as admin_router

app.include_router(chat_router)
app.include_router(admin_router)

from pathlib import Path
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

@app.get("/health")
async def health():
    """Liveness probe: the process is answering requests."""
    return {"status": "ok", "gateway": "online"}


@app.get("/ready")
async def ready():
    """Readiness probe used by the deploy platform before routing traffic."""
    checks = {"database": "unavailable", "redis": "unavailable"}
    try:
        async with engine.connect() as connection:
            await asyncio.wait_for(connection.execute(text("SELECT 1")), timeout=3)
        checks["database"] = "ok"
    except Exception:
        pass

    try:
        await asyncio.wait_for(redis_client.ping(), timeout=3)
        checks["redis"] = "ok"
    except Exception:
        pass

    is_ready = all(value == "ok" for value in checks.values())
    return JSONResponse(
        status_code=200 if is_ready else 503,
        content={"status": "ready" if is_ready else "not_ready", "checks": checks},
    )

static_dir = Path(__file__).parent / "static"

# Mount Vite assets
if (static_dir / "assets").exists():
    app.mount("/assets", StaticFiles(directory=static_dir / "assets"), name="assets")

@app.get("/", response_class=HTMLResponse)
async def root():
    index_path = static_dir / "index.html"
    return HTMLResponse(index_path.read_text(encoding="utf-8"))
