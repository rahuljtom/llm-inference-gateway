from pydantic import SecretStr

from app.core.tokens import estimate_request_tokens
from app.middleware.ratelimit import _estimate_tokens_from_json
from app.models.chat import ChatCompletionBody, ChatMessage, GatewayChatRequest


def test_estimate_tokens_from_json():
    body = {
        "messages": [{"role": "user", "content": "hello world"}],
        "max_tokens": 500,
    }
    estimate = _estimate_tokens_from_json(body)
    assert estimate > 500


def test_estimate_request_tokens():
    request = GatewayChatRequest(
        provider="groq",
        api_key=SecretStr("gsk_x"),
        model="llama-3.1-8b-instant",
        messages=[ChatMessage(role="user", content="test message here")],
        max_tokens=256,
    )
    assert estimate_request_tokens(request) >= 256
