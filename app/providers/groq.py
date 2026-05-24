import httpx

from app.providers.openai_compatible import OpenAICompatibleProvider

GROQ_CHAT_URL = "https://api.groq.com/openai/v1/chat/completions"


class GroqProvider(OpenAICompatibleProvider):
    def __init__(self, client: httpx.AsyncClient, upstream_api_key: str):
        super().__init__(client, upstream_api_key, GROQ_CHAT_URL)
