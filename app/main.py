from contextlib import asynccontextmanager
from fastapi import FastAPI
import httpx

from app.routes import chat

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize shared HTTP client for all downstream provider requests
    # This prevents socket exhaustion under load
    app.state.http_client = httpx.AsyncClient(timeout=60.0)
    yield
    # Clean up gracefully on shutdown
    await app.state.http_client.aclose()

app = FastAPI(
    title="LLM Inference Gateway",
    description="Production-shaped OpenAI-compatible gateway",
    version="0.1.0",
    lifespan=lifespan
)

app.include_router(chat.router)

@app.get("/health")
async def health():
    return {"status": "ok", "gateway": "online"}
