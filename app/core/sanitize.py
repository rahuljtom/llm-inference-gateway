SENSITIVE_KEYS = frozenset({"api_key", "authorization", "x-api-key", "x-provider-api-key"})


def redact_mapping(data: dict) -> dict:
    return {
        key: "***" if key.lower() in SENSITIVE_KEYS else value
        for key, value in data.items()
    }
