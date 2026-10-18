from app.models.chat import ChatMessage, GatewayChatRequest
from app.providers.gemini import GeminiProvider


def test_gemini_3_payload_omits_unsupported_temperature():
    request = GatewayChatRequest(
        provider="gemini",
        model="gemini-3.8-flash",
        api_key="test-key",
        messages=[ChatMessage(role="user", content="hello")],
        temperature=1.0,
    )

    payload = GeminiProvider(None, "test-key")._payload(request)

    assert "temperature" not in payload
    assert payload["model"] == "gemini-3.8-flash"


def test_older_gemini_payload_keeps_temperature():
    request = GatewayChatRequest(
        provider="gemini",
        model="gemini-2.5-flash",
        api_key="test-key",
        messages=[ChatMessage(role="user", content="hello")],
        temperature=0.5,
    )

    payload = GeminiProvider(None, "test-key")._payload(request)

    assert payload["temperature"] == 0.5
