"""Static aliases and validated, environment-configured route policies."""

import json
import math
from dataclasses import dataclass
from typing import Optional

from app.core.settings import settings

ROUTING_ALIASES = {
    "fast-chat": ("groq", "llama-3.1-8b-instant"),
    "smart-chat": ("openai", "gpt-4o"),
    "claude-chat": ("anthropic", "claude-3-5-sonnet-20241022"),
    "gemini-chat": ("gemini", "gemini-1.5-flash"),
}
SUPPORTED_PROVIDERS = frozenset({"openai", "groq", "anthropic", "gemini"})


@dataclass(frozen=True)
class RouteCandidate:
    provider: str
    model: str
    estimated_cost_per_1k_tokens_usd: Optional[float] = None
    expected_p95_latency_ms: Optional[float] = None
    timeout_seconds: Optional[float] = None
    max_retries: Optional[int] = None


def _positive_number(value, name: str, *, zero_allowed: bool = False) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{name} must be a number") from error
    if not math.isfinite(number) or (number < 0 if zero_allowed else number <= 0):
        raise ValueError(f"{name} must be {'non-negative' if zero_allowed else 'positive'}")
    return number


def configured_policies() -> dict:
    raw = settings.ROUTING_POLICIES_JSON
    if not raw:
        return {}
    try:
        policies = json.loads(raw)
    except json.JSONDecodeError as error:
        raise ValueError("ROUTING_POLICIES_JSON must contain valid JSON") from error
    if not isinstance(policies, dict):
        raise ValueError("ROUTING_POLICIES_JSON must be a JSON object")
    return {str(alias).strip().lower(): policy for alias, policy in policies.items()}


def resolve_route_candidates(model: str) -> list[RouteCandidate]:
    alias = model.strip().lower()
    policies = configured_policies()
    if alias in policies:
        policy = policies[alias]
        if not isinstance(policy, dict):
            raise ValueError(f"route policy for {alias} must be an object")
        candidates = policy.get("candidates")
        if not isinstance(candidates, list) or not candidates:
            raise ValueError(f"route policy for {alias} must include candidates")
        strategy = policy.get("strategy", "lowest_cost")
        if strategy not in {"lowest_cost", "lowest_latency"}:
            raise ValueError(f"unsupported route strategy for {alias}")
        max_cost = policy.get("max_estimated_cost_per_1k_tokens_usd")
        max_latency = policy.get("max_p95_latency_ms")
        max_cost = _positive_number(max_cost, "max_estimated_cost_per_1k_tokens_usd", zero_allowed=True) if max_cost is not None else None
        max_latency = _positive_number(max_latency, "max_p95_latency_ms") if max_latency is not None else None

        parsed: list[RouteCandidate] = []
        for candidate in candidates:
            if not isinstance(candidate, dict):
                raise ValueError("route candidates must be objects")
            provider = str(candidate.get("provider", "")).strip().lower()
            model_name = str(candidate.get("model", "")).strip()
            if provider not in SUPPORTED_PROVIDERS or not model_name:
                raise ValueError("route candidates need a supported provider and model")
            cost = _positive_number(
                candidate.get("estimated_cost_per_1k_tokens_usd"),
                "estimated_cost_per_1k_tokens_usd",
                zero_allowed=True,
            )
            p95 = _positive_number(candidate.get("expected_p95_latency_ms"), "expected_p95_latency_ms")
            timeout = _positive_number(candidate.get("timeout_seconds"), "timeout_seconds")
            if timeout > 120:
                raise ValueError("timeout_seconds must not exceed 120")
            retries = candidate.get("max_retries", 1)
            if isinstance(retries, bool) or not isinstance(retries, int) or not 0 <= retries <= 2:
                raise ValueError("max_retries must be an integer from 0 to 2")
            if max_cost is not None and cost > max_cost:
                continue
            if max_latency is not None and p95 > max_latency:
                continue
            parsed.append(RouteCandidate(provider, model_name, cost, p95, timeout, retries))

        if not parsed:
            raise ValueError(f"no route candidates meet the configured limits for {alias}")
        if strategy == "lowest_cost":
            return sorted(parsed, key=lambda item: (item.estimated_cost_per_1k_tokens_usd, item.expected_p95_latency_ms))
        return sorted(parsed, key=lambda item: (item.expected_p95_latency_ms, item.estimated_cost_per_1k_tokens_usd))

    static = ROUTING_ALIASES.get(alias)
    if static:
        return [RouteCandidate(provider=static[0], model=static[1])]
    return []


def resolve_route(model: str) -> tuple[Optional[str], str]:
    """Resolve a model alias to the first candidate or leave concrete names unchanged."""
    candidates = resolve_route_candidates(model)
    if candidates:
        return candidates[0].provider, candidates[0].model
    return None, model
