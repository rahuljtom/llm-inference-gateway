from app.core.cache import build_cache_key


def test_cache_key_stable_and_excludes_secrets():
    payload = {
        "model": "llama-3.1-8b-instant",
        "messages": [{"role": "user", "content": "hi"}],
        "temperature": 1.0,
    }
    k1 = build_cache_key(1, "groq", "llama-3.1-8b-instant", payload)
    k2 = build_cache_key(1, "groq", "llama-3.1-8b-instant", payload)
    k3 = build_cache_key(2, "groq", "llama-3.1-8b-instant", payload)

    assert k1 == k2
    assert k1 != k3
    assert k1.startswith("cache:")
    assert "gsk" not in k1
