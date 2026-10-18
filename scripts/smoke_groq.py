import asyncio
import httpx


async def main():
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
        response.raise_for_status()
        try:
            print("Response:", response.json())
        except Exception:
            print("Text:", response.text)

if __name__ == "__main__":
    asyncio.run(main())
