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
