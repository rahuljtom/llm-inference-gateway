import httpx
import pytest
from fastapi import Request
from pydantic import SecretStr
from unittest.mock import patch

from app.models.chat import ChatCompletionBody, GatewayChatRequest, ChatMessage
from app.services.inference import execute_completion, FallbackConfig


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
