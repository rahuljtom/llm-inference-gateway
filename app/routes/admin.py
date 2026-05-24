from datetime import datetime, timedelta
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from sqlalchemy import func
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.db.session import engine
from app.models.db import RequestLog

router = APIRouter(tags=["admin"])

_ADMIN_HTML = Path(__file__).resolve().parent.parent / "static" / "admin.html"


@router.get("/admin", response_class=HTMLResponse)
async def admin_dashboard():
    return HTMLResponse(_ADMIN_HTML.read_text(encoding="utf-8"))


@router.get("/admin/api/stats")
async def admin_stats():
    # RequestLog.created_at is stored as naive UTC (TIMESTAMP WITHOUT TIME ZONE).
    since = datetime.utcnow() - timedelta(hours=24)

    async with AsyncSession(engine) as session:
        total = (
            await session.exec(
                select(func.count(RequestLog.id)).where(RequestLog.created_at >= since)
            )
        ).one()
        cached_hits = (
            await session.exec(
                select(func.count(RequestLog.id)).where(
                    RequestLog.created_at >= since,
                    RequestLog.cached == True,  # noqa: E712
                )
            )
        ).one()
        fallback_hits = (
            await session.exec(
                select(func.count(RequestLog.id)).where(
                    RequestLog.created_at >= since,
                    RequestLog.fallback_used == True,  # noqa: E712
                )
            )
        ).one()
        avg_latency = (
            await session.exec(
                select(func.avg(RequestLog.latency_ms)).where(
                    RequestLog.created_at >= since
                )
            )
        ).one()
        token_sum = (
            await session.exec(
                select(func.sum(RequestLog.total_tokens)).where(
                    RequestLog.created_at >= since
                )
            )
        ).one()

        by_provider_result = await session.exec(
            select(
                RequestLog.provider,
                func.count(RequestLog.id).label("requests"),
                func.sum(RequestLog.total_tokens).label("tokens"),
            )
            .where(RequestLog.created_at >= since)
            .group_by(RequestLog.provider)
        )
        by_provider = [
            {"provider": row[0], "requests": row[1], "tokens": int(row[2] or 0)}
            for row in by_provider_result.all()
        ]

        hour_bucket = func.date_trunc("hour", RequestLog.created_at).label("hour")
        hourly_result = await session.exec(
            select(
                hour_bucket,
                func.count(RequestLog.id).label("requests"),
            )
            .where(RequestLog.created_at >= since)
            .group_by(hour_bucket)
            .order_by(hour_bucket)
        )
        hourly = [
            {"hour": row[0].isoformat() if row[0] else None, "requests": row[1]}
            for row in hourly_result.all()
        ]

    total = total or 0
    return {
        "window_hours": 24,
        "total_requests": total,
        "cache_hit_rate": round((cached_hits or 0) / total, 4) if total else 0.0,
        "fallback_rate": round((fallback_hits or 0) / total, 4) if total else 0.0,
        "avg_latency_ms": round(float(avg_latency or 0), 1),
        "total_tokens": int(token_sum or 0),
        "by_provider": by_provider,
        "hourly_requests": hourly,
    }
