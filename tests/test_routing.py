import json

import pytest

from app.core.settings import settings
from app.models.chat import ChatCompletionBody, ChatMessage
from app.services.inference import _resolve_fallback
from app.services.ingress import build_gateway_request
from app.services.routing import resolve_route_candidates
from starlette.requests import Request


def _policy():
    return {
        "team-chat": {
            "strategy": "lowest_cost",
            "max_estimated_cost_per_1k_tokens_usd": 0.05,
            "max_p95_latency_ms": 1000,
            "candidates": [
                {
                    "provider": "openai", "model": "balanced-model",
                    "estimated_cost_per_1k_tokens_usd": 0.03,
                    "expected_p95_latency_ms": 700, "timeout_seconds": 10,
                    "max_retries": 1,
                },
                {
                    "provider": "groq", "model": "low-cost-model",
                    "estimated_cost_per_1k_tokens_usd": 0.01,
                    "expected_p95_latency_ms": 900, "timeout_seconds": 5,
                    "max_retries": 0,
                },
                {
                    "provider": "anthropic", "model": "too-slow",
                    "estimated_cost_per_1k_tokens_usd": 0.02,
                    "expected_p95_latency_ms": 1200, "timeout_seconds": 10,
                },
            ],
        }
    }


def test_route_policy_filters_cost_and_latency_then_sorts_by_strategy(monkeypatch):
    monkeypatch.setattr(settings, "ROUTING_POLICIES_JSON", json.dumps(_policy()))

    candidates = resolve_route_candidates("TEAM-CHAT")

    assert [(item.provider, item.model) for item in candidates] == [
        ("groq", "low-cost-model"),
        ("openai", "balanced-model"),
    ]
    assert candidates[0].timeout_seconds == 5
    assert candidates[0].max_retries == 0


def test_route_policy_fails_when_all_candidates_exceed_constraints(monkeypatch):
    policy = _policy()
    policy["team-chat"]["max_estimated_cost_per_1k_tokens_usd"] = 0
    monkeypatch.setattr(settings, "ROUTING_POLICIES_JSON", json.dumps(policy))

    with pytest.raises(ValueError, match="no route candidates"):
        resolve_route_candidates("team-chat")


def test_policy_routes_to_managed_key_and_builds_eligible_fallbacks(monkeypatch):
    monkeypatch.setattr(settings, "ROUTING_POLICIES_JSON", json.dumps(_policy()))
    monkeypatch.setattr(settings, "GROQ_API_KEY", "managed-groq")
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "managed-openai")
    request = Request({
        "type": "http", "method": "POST", "path": "/v1/chat/completions",
        "headers": [], "state": {},
    })
    body = ChatCompletionBody(
        model="team-chat", messages=[ChatMessage(role="user", content="hello")]
    )

    gateway_request = build_gateway_request(request, body)
    fallback = _resolve_fallback(request, body)

    assert gateway_request.provider == "groq"
    assert gateway_request.model == "low-cost-model"
    assert gateway_request.route_timeout_seconds == 5
    assert gateway_request.max_retries == 0
    assert "route_timeout_seconds" not in gateway_request.upstream_payload()
    assert fallback is not None
    assert [candidate.model for candidate in fallback.candidates] == ["balanced-model"]
    assert fallback.gateway_request.api_key.get_secret_value() == "managed-openai"


def test_invalid_route_policy_is_rejected(monkeypatch):
    monkeypatch.setattr(settings, "ROUTING_POLICIES_JSON", "not-json")

    with pytest.raises(ValueError, match="valid JSON"):
        resolve_route_candidates("team-chat")
