# SDK DEMO (BYOK via headers — OpenAI-compatible body)

python -c "
from openai import OpenAI

client = OpenAI(
    base_url='http://127.0.0.1:8000/v1',
    api_key='demo-key',
    default_headers={
        'X-Provider': 'groq',
        'X-Provider-Api-Key': 'gsk_YOUR_GROQ_KEY',
    },
)

r = client.chat.completions.create(
    model='llama-3.1-8b-instant',
    messages=[{'role':'user','content':'hi'}],
)

print(r.choices[0].message.content)
"

# SDK DEMO (BYOK via extra_body)

python -c "
from openai import OpenAI

client = OpenAI(
    base_url='http://127.0.0.1:8000/v1',
    api_key='demo-key'
)

r = client.chat.completions.create(
    model='llama-3.1-8b-instant',
    messages=[{'role':'user','content':'hi'}],
    extra_body={
        'provider': 'groq',
        'api_key': 'gsk_YOUR_GROQ_KEY',
    },
)

print(r.choices[0].message.content)
"

# NON-STREAMING (headers)

curl http://127.0.0.1:8000/v1/chat/completions \
  -H "Authorization: Bearer demo-key" \
  -H "X-Provider: groq" \
  -H "X-Provider-Api-Key: gsk_YOUR_GROQ_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "llama-3.1-8b-instant",
    "messages": [{"role": "user", "content": "explain redis in one sentence"}]
  }'

# NON-STREAMING (body)

curl http://127.0.0.1:8000/v1/chat/completions \
  -H "Authorization: Bearer demo-key" \
  -H "Content-Type: application/json" \
  -d '{
    "provider": "groq",
    "api_key": "gsk_YOUR_GROQ_KEY",
    "model": "llama-3.1-8b-instant",
    "messages": [{"role": "user", "content": "explain llm gateways in one sentence"}]
  }'

# STREAMING (headers)

curl -N http://127.0.0.1:8000/v1/chat/completions \
  -H "Authorization: Bearer demo-key" \
  -H "X-Provider: groq" \
  -H "X-Provider-Api-Key: gsk_YOUR_GROQ_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "llama-3.1-8b-instant",
    "messages": [{"role": "user", "content": "count to 5"}],
    "stream": true
  }'

# WITH FALLBACK (body — used on timeout or 5xx)

curl http://127.0.0.1:8000/v1/chat/completions \
  -H "Authorization: Bearer demo-key" \
  -H "Content-Type: application/json" \
  -d '{
    "provider": "openai",
    "api_key": "sk_PRIMARY",
    "fallback_provider": "groq",
    "fallback_api_key": "gsk_FALLBACK",
    "fallback_model": "llama-3.1-8b-instant",
    "model": "gpt-4o-mini",
    "messages": [{"role": "user", "content": "hello"}]
  }'

# INVALID PROVIDER

curl -i http://127.0.0.1:8000/v1/chat/completions \
  -H "Authorization: Bearer demo-key" \
  -H "X-Provider: not-a-provider" \
  -H "X-Provider-Api-Key: gsk_YOUR_GROQ_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "llama-3.1-8b-instant",
    "messages": [{"role": "user", "content": "hi"}]
  }'
