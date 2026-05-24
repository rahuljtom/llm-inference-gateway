"""
Async sliding-window rate limiter using Redis Sorted Sets.

Adapted from github.com/rahuljtom/rate-limiter — ported from sync redis
to async redis-py for use inside the FastAPI gateway middleware.

Algorithm:
  1. Remove all entries outside the current sliding window
  2. Add the current request timestamp (with UUID for sub-ms uniqueness)
  3. Count entries remaining in the window
  4. If count > limit, reject with 429
"""

import time
import uuid
from dataclasses import dataclass

from app.core.redis import redis_client


@dataclass
class RateLimitResult:
    allowed: bool
    limit: int
    remaining: int
    retry_after: int  # seconds until the window resets (used in 429 header)


async def check_rate_limit(
    key: str,
    limit: int,
    window_seconds: int = 60
) -> RateLimitResult:
    """
    Sliding window rate limiter using Redis Sorted Sets.
    Mirrors the logic from the rate-limiter project but fully async.
    """
    redis_key = f"rl:{key}"
    now = time.time()
    window_start = now - window_seconds

    # Pipeline = atomic batch of Redis commands (single round-trip)
    pipeline = redis_client.pipeline()

    # 1. Evict timestamps older than the sliding window
    pipeline.zremrangebyscore(redis_key, 0, window_start)

    # 2. Add the current request with a unique member to handle sub-ms bursts
    pipeline.zadd(redis_key, {f"{now}-{uuid.uuid4()}": now})

    # 3. Count how many requests are in the current window
    pipeline.zcard(redis_key)

    # 4. Auto-expire the key so Redis doesn't leak memory
    pipeline.expire(redis_key, window_seconds)

    results = await pipeline.execute()

    current_count = results[2]  # zcard result

    return RateLimitResult(
        allowed=current_count <= limit,
        limit=limit,
        remaining=max(0, limit - current_count),
        retry_after=window_seconds
    )


def _parse_tpm_member(member: str) -> int:
    # member format: "{tokens}:{uuid}"
    return int(member.split(":", 1)[0])


async def get_tpm_usage(key: str, window_seconds: int = 60) -> int:
    redis_key = f"rl:tpm:{key}"
    now = time.time()
    window_start = now - window_seconds
    await redis_client.zremrangebyscore(redis_key, 0, window_start)
    members = await redis_client.zrange(redis_key, 0, -1)
    return sum(_parse_tpm_member(m) for m in members)


async def check_tpm_rate_limit(
    key: str,
    token_estimate: int,
    limit: int,
    window_seconds: int = 60,
) -> RateLimitResult:
    current = await get_tpm_usage(key, window_seconds)
    projected = current + token_estimate
    return RateLimitResult(
        allowed=projected <= limit,
        limit=limit,
        remaining=max(0, limit - projected),
        retry_after=window_seconds,
    )


async def record_tpm_usage(
    key: str,
    tokens: int,
    window_seconds: int = 60,
) -> None:
    if tokens <= 0:
        return
    redis_key = f"rl:tpm:{key}"
    now = time.time()
    member = f"{tokens}:{uuid.uuid4()}"
    pipeline = redis_client.pipeline()
    pipeline.zadd(redis_key, {member: now})
    pipeline.expire(redis_key, window_seconds)
    await pipeline.execute()
