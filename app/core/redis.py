import redis.asyncio as aioredis

from app.core.settings import settings

# Singleton async Redis connection pool, initialized once at import time.
# All middleware (rate limiter, cache) shares this pool.
redis_client = aioredis.from_url(
    settings.REDIS_URL,
    decode_responses=True
)
