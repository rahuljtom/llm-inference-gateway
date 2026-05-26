from typing import Optional, Tuple

# Static routing aliases for MVP.
# Keys are virtual model aliases.
# Values are (provider, actual_model).
ROUTING_ALIASES = {
    "fast-chat": ("groq", "llama-3.1-8b-instant"),
    "smart-chat": ("openai", "gpt-4o"),
    "claude-chat": ("anthropic", "claude-3-5-sonnet-20241022"),
    "gemini-chat": ("gemini", "gemini-1.5-flash"),
}


def resolve_route(model: str) -> Tuple[Optional[str], str]:
    """
    Resolve a virtual model name to a specific provider and upstream model.
    Returns (provider, mapped_model)
    If no alias is found, returns (None, model)
    """
    model_lower = model.strip().lower()
    if model_lower in ROUTING_ALIASES:
        return ROUTING_ALIASES[model_lower]
    return None, model
