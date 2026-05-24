from app.models.chat import ChatMessage, GatewayChatRequest

# Rough chars-per-token estimate for pre-request TPM checks
_CHARS_PER_TOKEN = 4
_DEFAULT_COMPLETION_RESERVE = 1024


def estimate_prompt_tokens(messages: list[ChatMessage]) -> int:
    chars = sum(len(m.content) for m in messages)
    return max(1, chars // _CHARS_PER_TOKEN)


def estimate_request_tokens(request: GatewayChatRequest) -> int:
    prompt = estimate_prompt_tokens(request.messages)
    completion_reserve = request.max_tokens or _DEFAULT_COMPLETION_RESERVE
    return prompt + completion_reserve
