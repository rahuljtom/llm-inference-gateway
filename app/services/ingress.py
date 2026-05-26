from fastapi import HTTPException, Request
from pydantic import SecretStr

from app.core.constants import X_PROVIDER, X_PROVIDER_API_KEY
from app.models.chat import ChatCompletionBody, GatewayChatRequest


from app.services.keys import resolve_managed_key
from app.services.routing import resolve_route

def resolve_credentials(request: Request, body: ChatCompletionBody) -> tuple[str, str, str]:
    """
    Resolve upstream provider, model, and API key.
    1. Check explicit provider in headers or body.
    2. If no explicit provider, attempt auto-routing based on model.
    3. Determine API key: explicit BYOK, else managed key.
    Returns (provider, model, api_key).
    """
    header_provider = request.headers.get(X_PROVIDER)
    header_api_key = request.headers.get(X_PROVIDER_API_KEY)

    explicit_provider = (header_provider or body.provider or "").strip().lower()
    
    # Routing
    routed_provider, routed_model = resolve_route(body.model)
    
    if explicit_provider:
        provider = explicit_provider
        model = routed_model
    else:
        if not routed_provider:
            raise HTTPException(
                status_code=400,
                detail=f"Missing explicit provider and model '{body.model}' is not auto-routable.",
            )
        provider = routed_provider
        model = routed_model

    # Credentials
    body_api_key = body.api_key.get_secret_value().strip() if body.api_key else ""
    explicit_api_key = (header_api_key or body_api_key or "").strip()

    if explicit_api_key:
        if explicit_api_key.strip() == "":
            raise HTTPException(
                status_code=400,
                detail=f"API key for {provider} cannot be empty or whitespace.",
            )
        api_key = explicit_api_key.strip()
    else:
        managed_key = resolve_managed_key(provider)
        if managed_key:
            api_key = managed_key
        else:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"No API key provided for {provider} and no managed key is configured. "
                    "Supply X-Provider-Api-Key header or api_key in the JSON body."
                ),
            )

    return provider, model, api_key


def build_gateway_request(
    request: Request, body: ChatCompletionBody
) -> GatewayChatRequest:
    provider, resolved_model, api_key = resolve_credentials(request, body)
    
    # The gateway request needs the potentially resolved model (e.g. fast-chat -> llama-3.1-8b-instant)
    # So we'll override the model when creating the GatewayChatRequest
    
    # We can pass model=resolved_model to to_gateway
    # but currently to_gateway only takes provider and api_key.
    # Let's modify what it takes, or just override it post-creation.
    req = body.to_gateway(provider=provider, api_key=SecretStr(api_key))
    req.model = resolved_model
    return req

