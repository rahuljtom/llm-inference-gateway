import httpx

from app.providers.openai_compatible import OpenAICompatibleProvider

OPENAI_CHAT_URL = "https://api.openai.com/v1/chat/completions"


class OpenAIProvider(OpenAICompatibleProvider):
    def __init__(self, client: httpx.AsyncClient, upstream_api_key: str):
        super().__init__(client, upstream_api_key, OPENAI_CHAT_URL)
