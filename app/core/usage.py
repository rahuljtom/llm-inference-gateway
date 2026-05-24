from typing import Any, Dict, Optional

from app.core.pricing import estimate_cost_usd
from app.models.chat import ChatCompletionResponse


def usage_from_response(response: ChatCompletionResponse) -> Dict[str, int]:
    usage = response.usage or {}
    prompt = int(usage.get("prompt_tokens", 0))
    completion = int(usage.get("completion_tokens", 0))
    total = int(usage.get("total_tokens", prompt + completion))
    return {
        "prompt_tokens": prompt,
        "completion_tokens": completion,
        "total_tokens": total,
    }


def set_request_usage(
    request_state: Any,
    *,
    model: str,
    usage: Optional[Dict[str, int]] = None,
) -> None:
    usage = usage or {}
    prompt = usage.get("prompt_tokens", 0)
    completion = usage.get("completion_tokens", 0)
    total = usage.get("total_tokens", prompt + completion)
    request_state.prompt_tokens = prompt
    request_state.completion_tokens = completion
    request_state.total_tokens = total
    request_state.cost_usd = estimate_cost_usd(model, prompt, completion)
