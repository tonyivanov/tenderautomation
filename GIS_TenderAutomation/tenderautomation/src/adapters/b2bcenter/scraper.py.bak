from __future__ import annotations

import asyncio
import random
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

import yaml
from bs4 import BeautifulSoup

from core.logging import get_logger
from core.models import PlatformDescriptor, RawTender
from .parsers import parse_rows, parse_total_count, B2BCenterRawRow

log = get_logger(__name__)

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
}


class B2BCenterScraper:
    def __init__(self, descriptor: PlatformDescriptor, queries_path: Path, cookies: dict | None = None) -> None:
        self._descriptor = descriptor
        self._queries_path = queries_path
        self._cookies = cookies or {}
        self._base_url = descriptor.base_url
        self._max_results = descriptor.extra.get("max_results_per_query", 1000)
        self._page_size = descriptor.extra.get("page_size", 20)
        self._incremental_stop = descriptor.extra.get("incremental_stop_after", 5)

    # ── Public API ────────────────────────────────────────────────────────

    async def fetch_new(self, since: datetime | None = None) -> list[RawTender]:
        """Fetch tenders via Playwright browser (bypasses CAPTCHA)."""
        from playwright.async_api import async_playwright
        import os as _os

        # Use proxy if configured
        proxy_raw = _os.getenv("HTTPS_PROXY", "")
        proxy = None
        if proxy_raw:
            # Parse http://user:pass@host:port
            import re as _re
            m = _re.match(r'https?://([^:]+):([^@]+)@([^:]+):(\d+)', proxy_raw)
            if m:
                proxy = {"server": f"http://{m.group(3)}:{m.group(4)}", "username": m.group(1), "password": m.group(2)}

        queries = self._load_queries()
        results: list[RawTender] = []

        pw = await async_playwright().start()
        try:
            launch_kwargs = {
                "headless": True,
                "args": ["--no-sandbox", "--disable-blink-features=AutomationControlled"],
            }
            if proxy:
                launch_kwargs["proxy"] = proxy
            browser = await pw.chromium.launch(**launch_kwargs)
            context = await browser.new_context(
                user_agent=BROWSER_HEADERS["User-Agent"],
                locale="ru-RU",
                timezone_id="Europe/Moscow",
                viewport={"width": 1920, "height": 1080},
            )
            await context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3,4,5]});
                Object.defineProperty(navigator, 'languages', {get: () => ['ru-RU','ru','en-US','en']});
            """)
            page = await context.new_page()

            try:
                for query in queries:
                    try:
                        batch = await self._fetch_query(page, query, since)
                        results.extend(batch)
                    except Exception as e:
                        log.warning(
                            "b2bcenter_query_failed",
                            extra={"context": {"query": query, "error": str(e)}},
                        )
                    await self._antibot_sleep()
            finally:
                await browser.close()
        finally:
            await pw.stop()

        return results

    # ── Per-query logic ────────────────────────────────────────────────────

    async def _fetch_query(
        self, page, query: str, since: datetime | None
    ) -> list[RawTender]:
        base_search_url = f"{self._base_url}/market/?search={quote(query)}"

        # Fetch first page
        await page.goto(base_search_url, wait_until="domcontentloaded", timeout=30000)
        html = await page.content()
        soup = BeautifulSoup(html, "html.parser")

        # Detect CAPTCHA — retry once with a pause
        if self._is_captcha(soup):
            log.warning("b2bcenter_captcha_retry", extra={"context": {"query": query}})
            await asyncio.sleep(random.uniform(10, 15))
            await page.goto(base_search_url, wait_until="domcontentloaded", timeout=30000)
            html = await page.content()
            soup = BeautifulSoup(html, "html.parser")
            if self._is_captcha(soup):
                log.error("b2bcenter_captcha_persistent", extra={"context": {"query": query}})
                return []

        total = parse_total_count(soup)

        if total is None or total > self._max_results:
            if total is not None:
                log.warning(
                    "noisy_query_skipped",
                    extra={"context": {"query": query, "total": total}},
                )
            return []

        results: list[RawTender] = []
        offset = 0

        while offset < total:
            if offset > 0:
                url = f"{base_search_url}&from={offset}"
                await self._antibot_sleep()
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                html = await page.content()
                soup = BeautifulSoup(html, "html.parser")

            rows = parse_rows(html, search_query=query)
            if not rows:
                break

            for row in rows:
                if since and self._row_is_older(row, since):
                    return results
                results.append(self._row_to_raw(row))

            offset += self._page_size

        log.info(
            "b2bcenter_query_done",
            extra={"context": {"query": query, "found": len(results)}},
        )
        return results

    # ── Helpers ────────────────────────────────────────────────────────────

    def _is_captcha(self, soup: BeautifulSoup) -> bool:
        """Detect CAPTCHA / challenge page."""
        text = soup.get_text().lower()
        if "captcha" in text:
            return True
        if "продолжить" in text and len(soup.get_text().strip()) < 100:
            return True
        if soup.find("title") and "just a moment" in (soup.find("title").string or "").lower():
            return True
        return False

    def _row_to_raw(self, row: B2BCenterRawRow) -> RawTender:
        return RawTender(
            platform="b2bcenter",
            external_id=row.lot_id,
            raw={
                "lot_id": row.lot_id,
                "title": row.title,
                "buyer": row.buyer,
                "budget_raw": row.budget_raw,
                "deadline_raw": row.deadline_raw,
                "url": row.url,
                "search_query": row.search_query,
            },
        )

    def _row_is_older(self, row: B2BCenterRawRow, since: datetime) -> bool:
        from .parsers import parse_deadline
        deadline = parse_deadline(row.deadline_raw)
        if deadline and deadline < since:
            return True
        return False

    async def _antibot_sleep(self) -> None:
        if random.random() < self._descriptor.extra.get("long_pause_prob", 0.15):
            delay = random.uniform(
                self._descriptor.extra.get("long_pause_sec_min", 8.0),
                self._descriptor.extra.get("long_pause_sec_max", 15.0),
            )
        else:
            delay = random.uniform(
                self._descriptor.extra.get("rate_limit_sec_min", 1.5),
                self._descriptor.extra.get("rate_limit_sec_max", 4.0),
            )
        await asyncio.sleep(delay)

    def _load_queries(self) -> list[str]:
        with open(self._queries_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return [str(q) for q in data.get("queries", [])]
