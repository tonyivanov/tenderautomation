"""Quick check of Groq API key validity."""
import os

import httpx

KEY = os.environ.get("GROQ_API_KEY")
if not KEY:
    raise SystemExit("GROQ_API_KEY is not set")

r = httpx.get("https://api.groq.com/openai/v1/models",
              headers={"Authorization": f"Bearer {KEY}"})
print(f"Status: {r.status_code}")
if r.status_code == 200:
    models = r.json().get("data", [])
    for m in models:
        print(f"  {m['id']}")
else:
    print("Error: provider rejected the request; response body omitted")
