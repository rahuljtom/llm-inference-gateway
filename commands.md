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

# NON-STREAMING

curl http://127.0.0.1:8000/v1/chat/completions \
  -H "Authorization: Bearer demo-key" \
  -H "Content-Type: application/json" \
  -d '{
    "provider": "groq",
    "api_key": "gsk_YOUR_GROQ_KEY",
    "model": "llama-3.1-8b-instant",
    "messages": [{"role": "user", "content": "explain redis in one sentence"}]
  }'

curl http://127.0.0.1:8000/v1/chat/completions \
  -H "Authorization: Bearer demo-key" \
  -H "Content-Type: application/json" \
  -d '{
    "provider": "groq",
    "api_key": "gsk_YOUR_GROQ_KEY",
    "model": "llama-3.1-8b-instant",
    "messages": [{"role": "user", "content": "explain llm gateways in one sentence"}]
  }'

# STREAMING

curl -N http://127.0.0.1:8000/v1/chat/completions \
  -H "Authorization: Bearer demo-key" \
  -H "Content-Type: application/json" \
  -d '{
    "provider": "groq",
    "api_key": "gsk_YOUR_GROQ_KEY",
    "model": "llama-3.1-8b-instant",
    "messages": [{"role": "user", "content": "count to 5"}],
    "stream": true
  }'

# INVALID PROVIDER

curl -i http://127.0.0.1:8000/v1/chat/completions \
  -H "Authorization: Bearer demo-key" \
  -H "Content-Type: application/json" \
  -d '{
    "provider": "not-a-provider",
    "api_key": "gsk_YOUR_GROQ_KEY",
    "model": "llama-3.1-8b-instant",
    "messages": [{"role": "user", "content": "hi"}]
  }'
