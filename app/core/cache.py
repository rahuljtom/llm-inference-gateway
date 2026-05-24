import hashlib
import json
from typing import Any, Dict, Optional

from app.core.redis import redis_client
from app.core.settings import settings


def build_cache_key(
    api_key_id: int,
    provider: str,
    model: str,
    payload: Dict[str, Any],
) -> str:
    """Exact-match cache key — excludes upstream secrets."""
    canonical = json.dumps(
        {
            "provider": provider,
            "model": model,
            "payload": payload,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    digest = hashlib.sha256(f"{api_key_id}:{canonical}".encode()).hexdigest()
    return f"cache:{digest}"


async def get_cached_response(cache_key: str) -> Optional[Dict[str, Any]]:
    if not settings.CACHE_ENABLED:
        return None
    raw = await redis_client.get(cache_key)
    if raw is None:
        return None
    return json.loads(raw)


async def set_cached_response(
    cache_key: str,
    response_data: Dict[str, Any],
) -> None:
    if not settings.CACHE_ENABLED:
        return
    await redis_client.setex(
        cache_key,
        settings.CACHE_TTL_SECONDS,
        json.dumps(response_data),
    )
