"""Redis-backed provider circuit breaker with a single half-open probe."""

import logging
import time

from app.core.redis import redis_client
from app.core.settings import settings

_ACQUIRE_SCRIPT = """
local state = redis.call('HGET', KEYS[1], 'state')
if state == 'open' then
    local opened_at = tonumber(redis.call('HGET', KEYS[1], 'opened_at') or '0')
    if tonumber(ARGV[1]) - opened_at < tonumber(ARGV[2]) then return 0 end
    redis.call('HSET', KEYS[1], 'state', 'half_open')
    redis.call('EXPIRE', KEYS[1], 86400)
    return 1
end
if state == 'half_open' then return 0 end
return 1
"""

_FAILURE_SCRIPT = """
local state = redis.call('HGET', KEYS[1], 'state')
if state == 'half_open' then
    redis.call('HSET', KEYS[1], 'state', 'open', 'opened_at', ARGV[1], 'failures', ARGV[2])
else
    local failures = redis.call('HINCRBY', KEYS[1], 'failures', 1)
    if failures >= tonumber(ARGV[2]) then
        redis.call('HSET', KEYS[1], 'state', 'open', 'opened_at', ARGV[1])
    end
end
redis.call('EXPIRE', KEYS[1], 86400)
return 1
"""


def _key(provider: str) -> str:
    return f"provider-circuit:{provider.strip().lower()}"


async def allow_provider_request(provider: str) -> bool:
    """Allow closed circuits and one probe after the open cooldown. Fail open on Redis errors."""
    try:
        return bool(await redis_client.eval(
            _ACQUIRE_SCRIPT,
            1,
            _key(provider),
            time.time(),
            settings.CIRCUIT_BREAKER_COOLDOWN_SECONDS,
        ))
    except Exception:
        logging.exception("Provider circuit state unavailable; allowing request")
        return True


async def record_provider_success(provider: str) -> None:
    """A successful request, including a half-open probe, closes the circuit."""
    try:
        await redis_client.delete(_key(provider))
    except Exception:
        logging.exception("Unable to clear provider circuit state")


async def record_provider_failure(provider: str) -> None:
    """Record a timeout or 5xx and open the circuit at its configured threshold."""
    try:
        await redis_client.eval(
            _FAILURE_SCRIPT,
            1,
            _key(provider),
            time.time(),
            max(1, settings.CIRCUIT_BREAKER_FAILURE_THRESHOLD),
        )
    except Exception:
        logging.exception("Unable to record provider circuit failure")
