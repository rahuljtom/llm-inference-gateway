from fastapi import HTTPException, Request
from pydantic import SecretStr

from app.core.constants import X_PROVIDER, X_PROVIDER_API_KEY
from app.models.chat import ChatCompletionBody, GatewayChatRequest


from app.services.keys import resolve_managed_key
from app.services.routing import configured_policies, resolve_route_candidates

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
    
    request.state.policy_route_fallbacks = []
    request.state.route_timeout_seconds = None
    request.state.route_max_retries = None
    route_candidates = resolve_route_candidates(body.model)
    policy_aliases = configured_policies()

    if explicit_provider:
        provider = explicit_provider
        model = route_candidates[0].model if route_candidates else body.model
    else:
        if not route_candidates:
            raise HTTPException(
                status_code=400,
                detail=f"Missing explicit provider and model '{body.model}' is not auto-routable.",
            )

    import logging
    body_api_key = body.api_key.get_secret_value().strip() if body.api_key else ""
    explicit_api_key = (header_api_key or body_api_key or "").strip()
    
    logging.info(f"Provider Auth Check: has_provider_key={bool(explicit_api_key)}")

    if explicit_provider:
        if explicit_api_key:
            api_key = explicit_api_key
        else:
            api_key = resolve_managed_key(provider)
        if not api_key:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"No API key provided for {provider} and no managed key is configured. "
                    "Supply X-Provider-Api-Key header or api_key in the JSON body."
                ),
            )
    else:
        candidates = route_candidates
        selected_index = None
        api_key = None
        for index, candidate in enumerate(candidates):
            candidate_key = explicit_api_key if index == 0 and explicit_api_key else resolve_managed_key(candidate.provider)
            if candidate_key:
                selected_index = index
                provider = candidate.provider
                model = candidate.model
                api_key = candidate_key
                request.state.route_timeout_seconds = candidate.timeout_seconds
                request.state.route_max_retries = candidate.max_retries
                break
        if selected_index is None or api_key is None:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"No managed provider key is configured for route alias '{body.model}'. "
                    "Supply an explicit provider and key, or configure a managed key."
                ),
            )
        if body.model.strip().lower() in policy_aliases:
            for candidate in candidates[selected_index + 1:]:
                candidate_key = resolve_managed_key(candidate.provider)
                if not candidate_key:
                    continue
                fallback_request = body.to_gateway(
                    provider=candidate.provider,
                    api_key=SecretStr(candidate_key),
                )
                fallback_request.model = candidate.model
                fallback_request.route_timeout_seconds = candidate.timeout_seconds
                fallback_request.max_retries = candidate.max_retries
                request.state.policy_route_fallbacks.append(fallback_request)

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
    req.route_timeout_seconds = getattr(request.state, "route_timeout_seconds", None)
    req.max_retries = getattr(request.state, "route_max_retries", None)
    return req

