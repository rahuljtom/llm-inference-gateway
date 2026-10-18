"""Authenticated, database-backed usage endpoints for the admin dashboard."""

from datetime import datetime, timedelta, timezone
from secrets import compare_digest, token_urlsafe
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Response
from pydantic import BaseModel, Field, field_validator
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.settings import settings
from app.core.security import hash_api_key
from app.db.session import engine
from app.models.db import APIKey, RequestLog, Team

router = APIRouter(prefix="/admin/api", tags=["admin"])


class APIKeyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    team: str = Field(min_length=1, max_length=120)
    rpm_limit: int = Field(default=60, ge=1, le=100000)
    tpm_limit: int = Field(default=100000, ge=1, le=100000000)

    @field_validator("name", "team")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value


async def require_admin_key(
    supplied_key: Annotated[Optional[str], Header(alias="X-Admin-API-Key")] = None,
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


@router.get("/keys", dependencies=[Depends(require_admin_key)])
async def list_api_keys():
    """List key metadata without exposing any credential material."""
    async with AsyncSession(engine) as session:
        rows = (
            await session.exec(
                select(APIKey, Team).outerjoin(Team, APIKey.team_id == Team.id)
                .order_by(APIKey.id)
            )
        ).all()
    return {
        "keys": [
            {
                "id": key.id,
                "name": key.name,
                "team": team.name if team else None,
                "rpmLimit": key.rpm_limit,
                "tpmLimit": key.tpm_limit,
                "revoked": key.revoked_at is not None,
                "createdAt": key.created_at.isoformat(),
            }
            for key, team in rows
        ]
    }


@router.post("/keys", status_code=201, dependencies=[Depends(require_admin_key)])
async def create_api_key(payload: APIKeyCreate):
    """Create a team-owned key and return its secret once."""
    raw_key = f"gw_{token_urlsafe(32)}"
    team_name = payload.team.casefold()
    async with AsyncSession(engine) as session:
        result = await session.exec(select(Team).where(Team.name == team_name))
        team = result.first()
        if team is None:
            team = Team(name=team_name)
            session.add(team)
            await session.flush()
        api_key = APIKey(
            key_hash=hash_api_key(raw_key),
            name=payload.name,
            team_id=team.id,
            rpm_limit=payload.rpm_limit,
            tpm_limit=payload.tpm_limit,
        )
        session.add(api_key)
        await session.commit()
        await session.refresh(api_key)
    return {
        "id": api_key.id,
        "name": api_key.name,
        "team": team.name,
        "key": raw_key,
        "rpmLimit": api_key.rpm_limit,
        "tpmLimit": api_key.tpm_limit,
        "createdAt": api_key.created_at.isoformat(),
    }


@router.delete("/keys/{key_id}", status_code=204, dependencies=[Depends(require_admin_key)])
async def revoke_api_key(key_id: int):
    """Revoke a key without deleting its request history."""
    async with AsyncSession(engine) as session:
        result = await session.exec(select(APIKey).where(APIKey.id == key_id))
        api_key = result.first()
        if api_key is None:
            raise HTTPException(status_code=404, detail="API key not found")
        if api_key.revoked_at is None:
            api_key.revoked_at = datetime.now(timezone.utc)
            await session.commit()
    return Response(status_code=204)
