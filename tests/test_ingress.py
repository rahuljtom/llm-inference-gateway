from typing import Dict, Optional

import pytest
from fastapi import HTTPException
from pydantic import SecretStr
from starlette.requests import Request

from app.models.chat import ChatCompletionBody, ChatMessage
from app.services.ingress import build_gateway_request, resolve_byok_credentials


def _request(headers: Optional[Dict[str, str]] = None) -> Request:
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/v1/chat/completions",
        "headers": [
            (k.lower().encode(), v.encode()) for k, v in (headers or {}).items()
        ],
    }
    return Request(scope)


def _body(**kwargs) -> ChatCompletionBody:
    defaults = {
        "model": "llama-3.1-8b-instant",
        "messages": [ChatMessage(role="user", content="hi")],
    }
    defaults.update(kwargs)
    return ChatCompletionBody(**defaults)


def test_resolve_from_body_only():
    request = _request()
    body = _body(provider="groq", api_key=SecretStr("gsk_test"))

    provider, api_key = resolve_byok_credentials(request, body)

    assert provider == "groq"
    assert api_key == "gsk_test"


def test_resolve_from_headers_only():
    request = _request(
        {
            "X-Provider": "openai",
            "X-Provider-Api-Key": "sk_test",
        }
    )
    body = _body()

    provider, api_key = resolve_byok_credentials(request, body)

    assert provider == "openai"
    assert api_key == "sk_test"


def test_headers_override_body():
    request = _request(
        {
            "X-Provider": "anthropic",
            "X-Provider-Api-Key": "ant_header",
        }
    )
    body = _body(provider="groq", api_key=SecretStr("gsk_body"))

    provider, api_key = resolve_byok_credentials(request, body)

    assert provider == "anthropic"
    assert api_key == "ant_header"


def test_missing_credentials_raises_400():
    request = _request()
    body = _body()

    with pytest.raises(HTTPException) as exc:
        resolve_byok_credentials(request, body)

    assert exc.value.status_code == 400


def test_whitespace_only_api_key_raises_400():
    request = _request()
    body = _body(provider="groq", api_key=SecretStr("   "))

    with pytest.raises(HTTPException) as exc:
        resolve_byok_credentials(request, body)

    assert exc.value.status_code == 400


def test_whitespace_only_header_api_key_raises_400():
    request = _request({"X-Provider": "groq", "X-Provider-Api-Key": "  \t"})
    body = _body()

    with pytest.raises(HTTPException) as exc:
        resolve_byok_credentials(request, body)

    assert exc.value.status_code == 400


def test_build_gateway_request():
    request = _request({"X-Provider": "groq", "X-Provider-Api-Key": "gsk_x"})
    body = _body()

    gateway = build_gateway_request(request, body)

    assert gateway.provider == "groq"
    assert gateway.api_key.get_secret_value() == "gsk_x"
    assert "api_key" not in gateway.upstream_payload()
