import pytest

from app.services import circuit_breaker


class FakeRedis:
    def __init__(self):
        self.values = {}

    async def eval(self, script, _numkeys, key, now, threshold_or_cooldown):
        entry = self.values.setdefault(key, {"state": "closed", "failures": 0})
        if script == circuit_breaker._ACQUIRE_SCRIPT:
            if entry["state"] == "open":
                if now - entry["opened_at"] < threshold_or_cooldown:
                    return 0
                entry["state"] = "half_open"
                return 1
            return int(entry["state"] != "half_open")

        if entry["state"] == "half_open":
            entry.update(state="open", opened_at=now, failures=threshold_or_cooldown)
        else:
            entry["failures"] += 1
            if entry["failures"] >= threshold_or_cooldown:
                entry.update(state="open", opened_at=now)
        return 1

    async def delete(self, key):
        self.values.pop(key, None)


@pytest.mark.anyio
async def test_circuit_opens_after_threshold_and_allows_one_recovery_probe(monkeypatch):
    redis = FakeRedis()
    monkeypatch.setattr(circuit_breaker, "redis_client", redis)
    monkeypatch.setattr(circuit_breaker.settings, "CIRCUIT_BREAKER_FAILURE_THRESHOLD", 2)
    monkeypatch.setattr(circuit_breaker.settings, "CIRCUIT_BREAKER_COOLDOWN_SECONDS", 30)
    clock = [100.0]
    monkeypatch.setattr(circuit_breaker.time, "time", lambda: clock[0])

    assert await circuit_breaker.allow_provider_request("openai")
    await circuit_breaker.record_provider_failure("openai")
    assert await circuit_breaker.allow_provider_request("openai")
    await circuit_breaker.record_provider_failure("openai")
    assert not await circuit_breaker.allow_provider_request("openai")

    clock[0] += 31
    assert await circuit_breaker.allow_provider_request("openai")
    assert not await circuit_breaker.allow_provider_request("openai")
    await circuit_breaker.record_provider_success("openai")
    assert await circuit_breaker.allow_provider_request("openai")


@pytest.mark.anyio
async def test_failed_half_open_probe_reopens_the_circuit(monkeypatch):
    redis = FakeRedis()
    monkeypatch.setattr(circuit_breaker, "redis_client", redis)
    monkeypatch.setattr(circuit_breaker.settings, "CIRCUIT_BREAKER_FAILURE_THRESHOLD", 1)
    monkeypatch.setattr(circuit_breaker.settings, "CIRCUIT_BREAKER_COOLDOWN_SECONDS", 10)
    clock = [100.0]
    monkeypatch.setattr(circuit_breaker.time, "time", lambda: clock[0])

    await circuit_breaker.record_provider_failure("groq")
    clock[0] += 11
    assert await circuit_breaker.allow_provider_request("groq")
    await circuit_breaker.record_provider_failure("groq")
    assert not await circuit_breaker.allow_provider_request("groq")


@pytest.mark.anyio
async def test_redis_errors_fail_open_without_breaking_requests(monkeypatch):
    class UnavailableRedis:
        async def eval(self, *_args):
            raise ConnectionError("redis unavailable")

        async def delete(self, *_args):
            raise ConnectionError("redis unavailable")

    monkeypatch.setattr(circuit_breaker, "redis_client", UnavailableRedis())

    assert await circuit_breaker.allow_provider_request("anthropic")
    await circuit_breaker.record_provider_failure("anthropic")
    await circuit_breaker.record_provider_success("anthropic")
