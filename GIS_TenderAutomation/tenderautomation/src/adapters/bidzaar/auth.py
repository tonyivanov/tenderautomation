from __future__ import annotations

import asyncio
import base64
import json
import os
import time
from pathlib import Path

from core.logging import get_logger
from core.models import AuthSession, PlatformCredentials, PlatformDescriptor

log = get_logger(__name__)


class BidzaarAuth:
    def __init__(self, descriptor: PlatformDescriptor) -> None:
        self._descriptor = descriptor
        self._state_path = Path(descriptor.extra.get("state_file", "data/bidzaar_state.json"))
        self._token_path = Path(descriptor.extra.get("token_cache_file", "data/bidzaar_token.json"))
        self._login_url = descriptor.extra.get("login_url", "https://bidzaar.com/auth/login")
        self._app_url = descriptor.extra.get("app_url", "https://bidzaar.com/requests/public")
        self._timeout = descriptor.extra.get("login_timeout_sec", 60)
        self._token_buffer = descriptor.extra.get("token_expiry_buffer_sec", 60)

    def get_session(self, credentials: PlatformCredentials) -> AuthSession:
        token = self._get_cached_token()
        if token:
            log.info("bidzaar_auth_cache_hit")
            return self._build_session(token)

        if self._state_path.exists():
            log.info("bidzaar_auth_headless_refresh")
            token = self._refresh_token_headless()
            if token:
                return self._build_session(token)
            log.warning("bidzaar_auth_state_stale")

        log.info("bidzaar_auth_full_login")
        token = self._full_auto_login(credentials)
        return self._build_session(token)

    async def async_get_session(self, credentials: PlatformCredentials) -> AuthSession:
        """Async version — safe to call inside asyncio event loop."""
        token = self._get_cached_token()
        if token:
            log.info("bidzaar_auth_cache_hit")
            return self._build_session(token)

        if self._state_path.exists():
            log.info("bidzaar_auth_headless_refresh_async")
            token = await self._refresh_token_headless_async()
            if token:
                return self._build_session(token)
            log.warning("bidzaar_auth_state_stale")

        log.info("bidzaar_auth_full_login")
        token = await asyncio.to_thread(self._full_auto_login, credentials)
        return self._build_session(token)

    # ── private ──────────────────────────────────────────────────────────

    def _get_cached_token(self) -> str | None:
        if not self._token_path.exists():
            return None
        try:
            data = json.loads(self._token_path.read_text(encoding="utf-8"))
            if data.get("expires_at", 0) - self._token_buffer > time.time():
                return data["access_token"]
        except (json.JSONDecodeError, OSError, KeyError):
            pass
        return None

    def _refresh_token_headless(self) -> str | None:
        """Sync version — used outside asyncio."""
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                context = browser.new_context(storage_state=str(self._state_path))
                page = context.new_page()
                try:
                    page.goto(self._app_url, wait_until="domcontentloaded", timeout=30000)
                except Exception:
                    return None
                time.sleep(3)
                token, expires_at = self._extract_token(page)
                if token:
                    context.storage_state(path=str(self._state_path))
                    self._save_token(token, expires_at)
                return token
            finally:
                browser.close()

    async def _refresh_token_headless_async(self) -> str | None:
        """Async version — used inside asyncio event loop."""
        from playwright.async_api import async_playwright
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            try:
                context = await browser.new_context(storage_state=str(self._state_path))
                page = await context.new_page()
                try:
                    await page.goto(self._app_url, wait_until="domcontentloaded", timeout=30000)
                except Exception:
                    return None
                await asyncio.sleep(3)
                token, expires_at = await self._extract_token_async(page)
                if token:
                    await context.storage_state(path=str(self._state_path))
                    self._save_token(token, expires_at)
                return token
            finally:
                await browser.close()

    def _full_auto_login(self, credentials: PlatformCredentials) -> str:
        from playwright.sync_api import sync_playwright
        self._state_path.parent.mkdir(parents=True, exist_ok=True)

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                context = browser.new_context()
                page = context.new_page()
                page.goto(self._login_url)

                # Fill login form (Bidzaar uses name="email" and name="password")
                page.fill('input[name="email"]', credentials.username)
                page.fill('input[name="password"]', credentials.password)
                page.click('button[type="submit"]')

                deadline = time.time() + self._timeout
                token, expires_at = None, 0
                while time.time() < deadline:
                    token, expires_at = self._extract_token(page)
                    if token:
                        break
                    time.sleep(2)

                if not token:
                    raise PermissionError(
                        f"Bidzaar auto-login failed: token not found after {self._timeout}s"
                    )

                context.storage_state(path=str(self._state_path))
                self._save_token(token, expires_at)
                log.info("bidzaar_auth_login_success")
                return token
            finally:
                browser.close()

    def _extract_token(self, page) -> tuple[str, int]:
        try:
            items = page.evaluate(
                "() => { const o={}; for(let i=0;i<localStorage.length;i++){"
                "const k=localStorage.key(i); o[k]=localStorage.getItem(k);} return o; }"
            )
        except Exception:
            return "", 0
        return self._parse_token_items(items)

    async def _extract_token_async(self, page) -> tuple[str, int]:
        try:
            items = await page.evaluate(
                "() => { const o={}; for(let i=0;i<localStorage.length;i++){"
                "const k=localStorage.key(i); o[k]=localStorage.getItem(k);} return o; }"
            )
        except Exception:
            return "", 0
        return self._parse_token_items(items)

    def _parse_token_items(self, items: dict) -> tuple[str, int]:
        token_raw = items.get("access_token", "")
        token = token_raw.strip().strip('"')
        if token.startswith("{"):
            try:
                token = json.loads(token).get("access_token", "")
            except json.JSONDecodeError:
                return "", 0
        if not token or "." not in token:
            return "", 0
        expires_at = self._decode_jwt_exp(token)
        return token, expires_at

    @staticmethod
    def _decode_jwt_exp(token: str) -> int:
        try:
            parts = token.split(".")
            if len(parts) < 2:
                return 0
            padding = "=" * ((4 - len(parts[1]) % 4) % 4)
            payload = json.loads(base64.urlsafe_b64decode(parts[1] + padding))
            return int(payload.get("exp", 0))
        except Exception:
            return 0

    def _save_token(self, token: str, expires_at: int) -> None:
        self._token_path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps({"access_token": token, "expires_at": expires_at})
        # Owner-only permissions: the bearer token must not be readable by
        # other processes on the host (especially in shared containers).
        fd = os.open(self._token_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(payload)

    def _build_session(self, token: str) -> AuthSession:
        cookies = {}
        if self._state_path.exists():
            try:
                state = json.loads(self._state_path.read_text(encoding="utf-8"))
                cookies = {c["name"]: c["value"] for c in state.get("cookies", [])}
            except (json.JSONDecodeError, OSError):
                pass
        return AuthSession(platform="bidzaar", token=token, cookies=cookies)
