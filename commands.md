# SDK DEMO

python -c "
from openai import OpenAI

client = OpenAI(
    base_url='http://127.0.0.1:8000/v1',
    api_key='demo-key'
)

r = client.chat.completions.create(
    model='llama-3.1-8b-instant',
    messages=[{'role':'user','content':'hi'}]
)

print(r.choices[0].message.content)
"

# NON-STREAMING

curl http://127.0.0.1:8000/v1/chat/completions \
  -H "Authorization: Bearer demo-key" \
  -H "Content-Type: application/json" \
  -d '{"model":"llama-3.1-8b-instant","messages":[{"role":"user","content":"explain redis in one sentence"}]}'

curl http://127.0.0.1:8000/v1/chat/completions \
  -H "Authorization: Bearer demo-key" \
  -H "Content-Type: application/json" \
  -d '{"model":"llama-3.1-8b-instant","messages":[{"role":"user","content":"explain llm gateways in one sentence"}]}'

# STREAMING

curl -N http://127.0.0.1:8000/v1/chat/completions \
  -H "Authorization: Bearer demo-key" \
  -H "Content-Type: application/json" \
  -d '{"model":"llama-3.1-8b-instant","messages":[{"role":"user","content":"count to 5"}],"stream":true}'

# INVALID MODEL

curl -i http://127.0.0.1:8000/v1/chat/completions \
  -H "Authorization: Bearer demo-key" \
  -H "Content-Type: application/json" \
  -d '{"model":"not-a-real-model","messages":[{"role":"user","content":"hi"}]}'