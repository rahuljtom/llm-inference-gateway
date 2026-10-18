# Static per-1M-token USD rates (input, output). Review time-sensitive rates before publishing estimates.
_MODEL_RATES: dict[str, tuple[float, float]] = {
    "gpt-4o": (2.50, 10.00),
    "gpt-4o-mini": (0.15, 0.60),
    "claude-3-5-sonnet": (3.00, 15.00),
    "claude-3-haiku": (0.25, 1.25),
    "llama-3.1-8b-instant": (0.05, 0.08),
    "llama-3.1-70b-versatile": (0.59, 0.79),
    # Groq GPT-OSS rates from https://console.groq.com/docs/models (2026-10-18).
    "openai/gpt-oss-20b": (0.075, 0.30),
    "openai/gpt-oss-120b": (0.15, 0.60),
    # Gemini 3.8 Flash introductory rates through 2026-12-31.
    "gemini-3.8-flash": (0.75, 3.75),
    # Anthropic Claude Sonnet 4.6 standard rates from https://docs.anthropic.com/en/docs/about-claude/pricing (2026-10-18).
    "claude-sonnet-4-6": (3.00, 15.00),
}


def estimate_cost_usd(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    input_rate, output_rate = (0.10, 0.10)
    for prefix, rates in _MODEL_RATES.items():
        if model.startswith(prefix) or model == prefix:
            input_rate, output_rate = rates
            break
    return (prompt_tokens * input_rate + completion_tokens * output_rate) / 1_000_000
