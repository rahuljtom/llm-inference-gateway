"""Authenticated, database-backed usage endpoints for the admin dashboard."""

from datetime import datetime, timedelta, timezone
from secrets import compare_digest
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.settings import settings
from app.db.session import engine
from app.models.db import RequestLog

router = APIRouter(prefix="/admin/api", tags=["admin"])


async def require_admin_key(
    supplied_key: Annotated[str | None, Header(alias="X-Admin-API-Key")] = None,
) -> None:
    """Fail closed when the admin secret is absent or does not match."""
    configured_key = settings.ADMIN_API_KEY
    if not configured_key:
        raise HTTPException(status_code=503, detail="Admin API is not configured")
    if not supplied_key or not compare_digest(supplied_key, configured_key):
        raise HTTPException(status_code=401, detail="Invalid admin API key")


@router.get("/stats", dependencies=[Depends(require_admin_key)])
async def get_stats():
    """Return real request and cost totals for the previous 24 hours."""
    since = datetime.now(timezone.utc) - timedelta(hours=24)
    async with AsyncSession(engine) as session:
        logs = (
            await session.exec(
                select(RequestLog).where(RequestLog.created_at >= since)
            )
        ).all()

    count = len(logs)
    return {
        "window": "24h",
        "requestCount": count,
        "avgLatencyMs": round(sum(row.latency_ms for row in logs) / count)
        if count
        else 0,
        "costUsd": round(sum(row.cost_usd for row in logs), 8),
        "cacheHitRatio": round(sum(row.cached for row in logs) / count, 4)
        if count
        else 0,
        "fallbackCount": sum(row.fallback_used for row in logs),
        "promptTokens": sum(row.prompt_tokens for row in logs),
        "completionTokens": sum(row.completion_tokens for row in logs),
    }


@router.get("/providers", dependencies=[Depends(require_admin_key)])
async def get_providers():
    """List supported providers without implying a live health probe."""
    return [
        {"name": name, "supported": True}
        for name in ("OpenAI", "Anthropic", "Gemini", "Groq")
    ]


@router.get("/metrics", dependencies=[Depends(require_admin_key)])
async def get_metrics():
    """Return per-minute request metrics over the last hour."""
    since = datetime.now(timezone.utc) - timedelta(hours=1)
    async with AsyncSession(engine) as session:
        logs = (
            await session.exec(
                select(RequestLog)
                .where(RequestLog.created_at >= since)
                .order_by(RequestLog.created_at)
            )
        ).all()

    buckets: dict[datetime, list[int]] = {}
    for row in logs:
        created_at = row.created_at
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        minute = created_at.replace(second=0, microsecond=0)
        bucket = buckets.setdefault(minute, [0, 0])
        bucket[0] += 1
        bucket[1] += row.latency_ms

    return [
        {
            "time": minute.isoformat(),
            "requestCount": values[0],
            "avgLatencyMs": round(values[1] / values[0]),
        }
        for minute, values in sorted(buckets.items())
    ]


@router.get("/requests/live", dependencies=[Depends(require_admin_key)])
async def get_live_requests():
    """Return recent request metadata without prompts or credentials."""
    async with AsyncSession(engine) as session:
        logs = (
            await session.exec(
                select(RequestLog).order_by(RequestLog.created_at.desc()).limit(10)
            )
        ).all()

    return {
        "requests": [
            {
                "id": row.id,
                "provider": row.provider,
                "model": row.model,
                "latencyMs": row.latency_ms,
                "totalTokens": row.total_tokens,
                "costUsd": row.cost_usd,
                "cached": row.cached,
                "fallbackUsed": row.fallback_used,
                "createdAt": row.created_at.isoformat(),
            }
            for row in logs
        ]
    }
