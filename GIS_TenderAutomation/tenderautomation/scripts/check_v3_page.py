"""Quick check: login and fetch /v3 page."""
import httpx

BASE = "http://127.0.0.1:8000"

# Use cookie jar to persist session
with httpx.Client(follow_redirects=False) as client:
    # Login
    r = client.post(f"{BASE}/login", data={
        "username": "analyst",
        "password": "pass123456",
    })
    print(f"Login: {r.status_code}, cookies: {dict(r.cookies)}")
    # Follow redirect to receive session cookie
    r2 = client.get(f"{BASE}/tenders")
    print(f"Tenders: {r2.status_code}, body len: {len(r2.text)}")

    # Now /v3 should work
    r = client.get(f"{BASE}/v3")
    print(f"/v3: {r.status_code}")
    if r.status_code == 200:
        print(f"Page length: {len(r.text)} chars")
        print("Contains P1:", "P1" in r.text)
        print("Contains P2:", "P2" in r.text)
        print("Contains Reject:", "Reject" in r.text)