from contextlib import asynccontextmanager
from fastapi import FastAPI
import httpx

from app.db.session import engine, init_db, seed_demo_api_key
from app.middleware.auth import AuthMiddleware
from app.middleware.ratelimit import RateLimitMiddleware
from app.middleware.logging import LoggingMiddleware
from app.routes import admin, chat

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

app.include_router(chat.router)
app.include_router(admin.router)

@app.get("/health")
async def health():
    return {"status": "ok", "gateway": "online"}
