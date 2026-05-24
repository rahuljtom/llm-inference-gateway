# Static per-1M-token USD rates (input, output) — Phase 2 will load from config/DB
_MODEL_RATES: dict[str, tuple[float, float]] = {
    "gpt-4o": (2.50, 10.00),
    "gpt-4o-mini": (0.15, 0.60),
    "claude-3-5-sonnet": (3.00, 15.00),
    "claude-3-haiku": (0.25, 1.25),
    "llama-3.1-8b-instant": (0.05, 0.08),
    "llama-3.1-70b-versatile": (0.59, 0.79),
}


def estimate_cost_usd(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    input_rate, output_rate = (0.10, 0.10)
    for prefix, rates in _MODEL_RATES.items():
        if model.startswith(prefix) or model == prefix:
            input_rate, output_rate = rates
            break
    return (prompt_tokens * input_rate + completion_tokens * output_rate) / 1_000_000
