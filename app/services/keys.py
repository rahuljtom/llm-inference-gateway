from typing import Optional

from app.core.settings import settings


def resolve_managed_key(provider: str) -> Optional[str]:
    """
    Attempt to resolve a managed API key for the given provider from settings.
    """
    provider = provider.strip().lower()
    if provider == "openai":
        return settings.OPENAI_API_KEY
    if provider == "anthropic":
        return settings.ANTHROPIC_API_KEY
    if provider == "groq":
        return settings.GROQ_API_KEY
    return None
