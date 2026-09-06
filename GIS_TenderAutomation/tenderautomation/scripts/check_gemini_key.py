"""Quick check of Gemini API key validity."""
import asyncio
import os
from google import genai

KEY = os.environ.get("GEMINI_API_KEY")
if not KEY:
    raise SystemExit("GEMINI_API_KEY is not set")

async def main():
    client = genai.Client(api_key=KEY)
    try:
        response = await client.aio.models.generate_content(
            model="gemini-2.5-flash",
            contents="Say 'OK' if you read this.",
        )
        print(f"Status: OK")
        print(f"Response: {response.text}")
        print(f"Usage: {response.usage_metadata}")
    except Exception as exc:
        print("Status: ERROR")
        print(f"Error type: {type(exc).__name__}")

asyncio.run(main())
