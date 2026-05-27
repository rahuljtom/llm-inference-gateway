import httpx
import asyncio

async def test_groq():
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://127.0.0.1:8000/v1/chat/completions",
            headers={"Authorization": "Bearer demo-key", "Content-Type": "application/json"},
            json={
                "model": "fast-chat",
                "messages": [{"role": "user", "content": "What is 2+2? Reply in one word."}]
            },
            timeout=10.0
        )
        print("Status:", response.status_code)
        try:
            print("Response:", response.json())
        except Exception:
            print("Text:", response.text)

if __name__ == "__main__":
    asyncio.run(test_groq())
