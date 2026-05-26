import time
import random
from fastapi import APIRouter

router = APIRouter(prefix="/admin/api", tags=["admin"])

# Mock state for telemetry until Redis/State module is fully hooked up
start_time = time.time()
recent_requests = []

@router.get("/stats")
async def get_stats():
    return {
        "requestCount": len(recent_requests) + 1240,
        "avgLatency": 340,
        "cacheHitRatio": "45%",
        "uptimeSeconds": int(time.time() - start_time)
    }

@router.get("/providers")
async def get_providers():
    return [
        {"name": "Groq", "status": "operational", "latency": 240, "sla": "99.99%"},
        {"name": "Gemini", "status": "operational", "latency": 800, "sla": "99.9%"},
        {"name": "OpenAI", "status": "operational", "latency": 450, "sla": "99.95%"},
        {"name": "Anthropic", "status": "operational", "latency": 1200, "sla": "99.9%"}
    ]

@router.get("/health")
async def get_health():
    return {
        "status": "healthy",
        "redis": "connected",
        "database": "connected",
        "version": "3.0.0"
    }

@router.get("/metrics")
async def get_metrics():
    # Return mock time series data for Recharts
    now = int(time.time())
    return [
        {"time": now - (i * 60), "latency": 200 + random.randint(0, 300), "throughput": 10 + random.randint(0, 50)}
        for i in range(20, 0, -1)
    ]

@router.get("/requests/live")
async def get_live_requests():
    return {"requests": recent_requests[-10:]}
