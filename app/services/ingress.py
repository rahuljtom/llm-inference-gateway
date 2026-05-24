from fastapi import HTTPException, Request
from pydantic import SecretStr

from app.core.constants import X_PROVIDER, X_PROVIDER_API_KEY
from app.models.chat import ChatCompletionBody, GatewayChatRequest


def resolve_byok_credentials(request: Request, body: ChatCompletionBody) -> tuple[str, str]:
    """
    Resolve upstream provider and API key from headers and/or body.
    Headers override body when both are present.
    """
    header_provider = request.headers.get(X_PROVIDER)
    header_api_key = request.headers.get(X_PROVIDER_API_KEY)

    provider = (header_provider or body.provider or "").strip().lower()
    body_api_key = body.api_key.get_secret_value().strip() if body.api_key else ""
    api_key = (header_api_key or body_api_key or "").strip()

    if not provider or not api_key:
        raise HTTPException(
            status_code=400,
            detail=(
                "Missing provider credentials. Supply X-Provider and "
                "X-Provider-Api-Key headers, or provider and api_key in the JSON body."
            ),
        )

    return provider, api_key


def build_gateway_request(
    request: Request, body: ChatCompletionBody
) -> GatewayChatRequest:
    provider, api_key = resolve_byok_credentials(request, body)
    return body.to_gateway(provider=provider, api_key=SecretStr(api_key))
