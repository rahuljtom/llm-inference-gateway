import httpx
import pytest
from fastapi import Request
from pydantic import SecretStr
from unittest.mock import patch

from app.models.chat import ChatCompletionBody, GatewayChatRequest, ChatMessage
from app.services.inference import execute_completion, execute_stream, FallbackConfig
from app.services.inference import _complete_with_provider


class DummyState:
    pass


@pytest.mark.anyio
async def test_inference_success():
    body = ChatCompletionBody(model="test", messages=[ChatMessage(role="user", content="hello")])
    req = GatewayChatRequest(provider="openai", model="test", api_key=SecretStr("key"), messages=body.messages)

    def handler(request):
        return httpx.Response(200, json={
            "id": "test", "created": 123, "model": "test", 
            "choices": [{"index": 0, "message": {"role": "assistant", "content": "hi"}, "finish_reason": "stop"}]
        })

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))

    app = type("App", (), {"state": type("AppState", (), {"http_client": client})()})()
    request = Request({"type": "http", "headers": [], "state": {}, "app": app})
    request.state.api_key = None

    res = await execute_completion(request, body, req, None)
    assert res.choices[0].message.content == "hi"


@pytest.mark.anyio
async def test_inference_fallback():
    body = ChatCompletionBody(model="test", messages=[ChatMessage(role="user", content="hello")])
    req = GatewayChatRequest(provider="openai", model="test", api_key=SecretStr("key"), messages=body.messages)
    fallback_req = GatewayChatRequest(provider="openai", model="test", api_key=SecretStr("fallback_key"), messages=body.messages)

    def handler(request):
        if "fallback_key" in request.headers.get("Authorization", ""):
                return httpx.Response(200, json={
                    "id": "test", "created": 123, "model": "test", 
                    "choices": [{"index": 0, "message": {"role": "assistant", "content": "fallback"}, "finish_reason": "stop"}]
                })
        return httpx.Response(500)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))

    app = type("App", (), {"state": type("AppState", (), {"http_client": client})()})()
    request = Request({"type": "http", "headers": [], "state": {}, "app": app})
    request.state.api_key = None
    request.state.fallback_used = False

    fallback = FallbackConfig(gateway_request=fallback_req)
    res = await execute_completion(request, body, req, fallback)
    assert res.choices[0].message.content == "fallback"
    assert request.state.fallback_used is True


@pytest.mark.anyio
@patch("app.services.inference.get_cached_response")
async def test_inference_cache_hit(mock_get_cached):
    mock_get_cached.return_value = {
        "id": "test", "created": 123, "model": "test", 
        "choices": [{"index": 0, "message": {"role": "assistant", "content": "cached"}, "finish_reason": "stop"}]
    }

    body = ChatCompletionBody(model="test", messages=[ChatMessage(role="user", content="hello")])
    req = GatewayChatRequest(provider="openai", model="test", api_key=SecretStr("key"), messages=body.messages)

    request = Request({"type": "http", "headers": [], "state": {}})
    request.state.api_key = type("ApiKey", (), {"id": 1})()
    request.state.cached = False

    res = await execute_completion(request, body, req, None)
    assert res.choices[0].message.content == "cached"
    assert request.state.cached is True


@pytest.mark.anyio
@patch("app.services.inference.set_cached_response")
@patch("app.services.inference.get_cached_response")
async def test_inference_cache_control_no_cache_bypasses_read_and_write(
    mock_get_cached, mock_set_cached
):
    body = ChatCompletionBody(model="test", messages=[ChatMessage(role="user", content="hello")])
    gateway_request = GatewayChatRequest(
        provider="openai", model="test", api_key=SecretStr("key"), messages=body.messages
    )

    def handler(_request):
        return httpx.Response(200, json={
            "id": "test", "created": 123, "model": "test",
            "choices": [{"index": 0, "message": {"role": "assistant", "content": "live"}, "finish_reason": "stop"}],
        })

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    app = type("App", (), {"state": type("AppState", (), {"http_client": client})()})()
    request = Request({"type": "http", "headers": [(b"cache-control", b"no-cache")], "state": {}, "app": app})
    request.state.api_key = type("ApiKey", (), {"id": 1})()
    request.state.cached = False

    result = await execute_completion(request, body, gateway_request, None)

    assert result.choices[0].message.content == "live"
    assert request.state.cached is False
    mock_get_cached.assert_not_awaited()
    mock_set_cached.assert_not_awaited()
    await client.aclose()


@pytest.mark.anyio
async def test_fallback_chain_tries_eligible_candidates_in_order(monkeypatch):
    body = ChatCompletionBody(model="primary", messages=[ChatMessage(role="user", content="hello")])
    primary = GatewayChatRequest(
        provider="openai", model="primary", api_key=SecretStr("primary"),
        messages=body.messages, max_retries=0,
    )
    first_fallback = GatewayChatRequest(
        provider="groq", model="unavailable", api_key=SecretStr("groq"),
        messages=body.messages, max_retries=0,
    )
    second_fallback = GatewayChatRequest(
        provider="anthropic", model="backup", api_key=SecretStr("anthropic"),
        messages=body.messages, max_retries=0,
    )

    class Provider:
        def __init__(self, outcome):
            self.outcome = outcome

        async def complete(self, _request):
            if isinstance(self.outcome, Exception):
                raise self.outcome
            return self.outcome

    def failed(status):
        request = httpx.Request("POST", "https://provider.test")
        response = httpx.Response(status, request=request)
        return httpx.HTTPStatusError("upstream", request=request, response=response)

    providers = {
        "openai": Provider(httpx.TimeoutException("primary timeout")),
        "groq": Provider(failed(503)),
        "anthropic": Provider({
            "id": "backup", "created": 1, "model": "backup",
            "choices": [{"index": 0, "message": {"role": "assistant", "content": "recovered"}, "finish_reason": "stop"}],
        }),
    }
    from app.models.chat import ChatCompletionResponse
    providers["anthropic"].outcome = ChatCompletionResponse(**providers["anthropic"].outcome)
    monkeypatch.setattr("app.services.inference.resolve_provider", lambda provider, *_args: providers[provider])
    app = type("App", (), {"state": type("AppState", (), {"http_client": None})()})()
    request = Request({"type": "http", "headers": [], "state": {}, "app": app})
    request.state.fallback_used = False

    result = await execute_completion(
        request,
        body,
        primary,
        FallbackConfig(first_fallback, [second_fallback]),
    )

    assert result.choices[0].message.content == "recovered"
    assert request.state.fallback_used is True
    assert request.state.provider == "anthropic"
    assert request.state.model == "backup"


@pytest.mark.anyio
async def test_route_retry_limit_controls_429_attempts(monkeypatch):
    import app.services.inference as inference

    class Provider:
        attempts = 0

        async def complete(self, _request):
            self.attempts += 1
            request = httpx.Request("POST", "https://provider.test")
            response = httpx.Response(429, request=request)
            raise httpx.HTTPStatusError("rate limited", request=request, response=response)

    provider = Provider()
    sleeps = []

    async def no_wait(delay):
        sleeps.append(delay)

    monkeypatch.setattr(inference.asyncio, "sleep", no_wait)
    gateway_request = GatewayChatRequest(
        provider="openai", model="limited", api_key=SecretStr("key"),
        messages=[ChatMessage(role="user", content="hello")], max_retries=1,
    )

    with pytest.raises(httpx.HTTPStatusError):
        await _complete_with_provider(provider, gateway_request)

    assert provider.attempts == 2
    assert sleeps == [1]


@pytest.mark.anyio
async def test_stream_returns_clear_error_when_circuit_is_open(monkeypatch):
    import app.services.inference as inference

    monkeypatch.setattr(inference, "allow_provider_request", lambda _provider: _async_value(False))
    gateway_request = GatewayChatRequest(
        provider="openai", model="unavailable", api_key=SecretStr("key"),
        messages=[ChatMessage(role="user", content="hello")], stream=True,
    )
    app = type("App", (), {"state": type("AppState", (), {"http_client": None})()})()
    request = Request({"type": "http", "headers": [], "state": {}, "app": app})
    chunks = [
        chunk async for chunk in execute_stream(
            request, gateway_request, None, budget_reserved=True
        )
    ]
    assert chunks == ['data: {"error": "No healthy upstream provider is available"}\n\n']


async def _async_value(value):
    return value
