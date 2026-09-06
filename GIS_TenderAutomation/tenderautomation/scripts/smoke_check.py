"""Runtime smoke checks executed inside the production application container."""
from __future__ import annotations

import os
import re
from http.cookies import SimpleCookie

import httpx
from playwright.sync_api import sync_playwright


BASE_URL = "http://127.0.0.1:8000"
USERNAME = "smoke@example.test"
PASSWORD = "smoke-password-123"


def _session_cookie(response: httpx.Response) -> str:
    cookies = SimpleCookie()
    cookies.load(response.headers["set-cookie"])
    morsel = cookies.get("session_id")
    if morsel is None:
        raise AssertionError("valid login did not set session_id")
    return morsel.value


def main() -> None:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_content("<title>TenderAutomation smoke</title>")
        assert page.title() == "TenderAutomation smoke"
        browser.close()

    with httpx.Client(base_url=BASE_URL, follow_redirects=False, timeout=15) as client:
        login_page = client.get("/login")
        assert login_page.status_code == 200
        assert "<form" in login_page.text

        expected_headers = {
            "cache-control": "no-store",
            "content-security-policy": None,
            "strict-transport-security": None,
            "x-content-type-options": "nosniff",
            "x-frame-options": "DENY",
        }
        for name, expected in expected_headers.items():
            assert name in login_page.headers
            if expected is not None:
                assert login_page.headers[name] == expected

        assert client.get("/").status_code == 302
        assert client.get("/tenders").status_code == 302
        assert client.post(
            "/login", data={"username": USERNAME, "password": "invalid-password"}
        ).status_code == 401

        login = client.post(
            "/login", data={"username": USERNAME, "password": PASSWORD}
        )
        assert login.status_code == 302
        session_id = _session_cookie(login)
        tenders = client.get(
            "/tenders", headers={"Cookie": f"session_id={session_id}"}
        )
        assert tenders.status_code == 200
        assert 'data-testid="tenders-tab-archive"' in tenders.text

        admin = client.get(
            "/admin", headers={"Cookie": f"session_id={session_id}"}
        )
        assert admin.status_code == 200
        assert 'data-testid="admin-commit-id"' in admin.text
        assert 'data-testid="deadline-reconcile-form"' in admin.text
        assert 'data-testid="deadline-reconcile-batch-size"' in admin.text
        assert 'data-testid="deadline-reconcile-submit"' in admin.text

        commit_sha = os.getenv("APP_COMMIT_SHA", "unknown").strip()
        expected_commit = (
            commit_sha[:8].lower()
            if re.fullmatch(r"[0-9a-fA-F]{8,64}", commit_sha)
            else "unknown"
        )
        assert f"commit {expected_commit}" in admin.text

    print("SMOKE_RESULT: passed")


if __name__ == "__main__":
    main()
