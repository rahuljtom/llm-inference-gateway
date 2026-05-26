import httpx

from app.providers.openai_compatible import OpenAICompatibleProvider

GEMINI_CHAT_URL = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"


class GeminiProvider(OpenAICompatibleProvider):
    def __init__(self, client: httpx.AsyncClient, upstream_api_key: str):
        super().__init__(client, upstream_api_key, GEMINI_CHAT_URL)
