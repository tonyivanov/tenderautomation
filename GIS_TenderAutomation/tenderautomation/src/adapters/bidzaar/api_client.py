from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import httpx

from core.logging import get_logger
from core.models import AuthSession, PlatformDescriptor, RawTender

log = get_logger(__name__)

LIST_URL = "https://bidzaar.com/api/process/light/procedures/available"


class TokenExpiredError(PermissionError):
    """Raised when the Bidzaar bearer token is rejected (HTTP 401) mid-fetch."""


class BidzaarApiClient:
    def __init__(self, session: AuthSession, descriptor: PlatformDescriptor) -> None:
        self._session = session
        self._descriptor = descriptor
        self._page_size = descriptor.extra.get("page_size", 25)
        self._rate_limit = descriptor.rate_limit_sec

    MAX_PAGES = 120  # ~3000 tenders per run
    INCREMENTAL_SKIP_STREAK = 999

    async def fetch_new(self, since: datetime | None = None) -> list[RawTender]:
        results: list[RawTender] = []
        page = 1
        total_count: int | None = None
        skipped_streak = 0
        now = datetime.now(timezone.utc)

        async with httpx.AsyncClient(headers=self._build_headers(), timeout=30.0) as client:
            while page <= self.MAX_PAGES:
                try:
                    data = await self._fetch_page(client, page)
                except httpx.HTTPStatusError as e:
                    if e.response.status_code == 401:
                        log.warning("bidzaar_token_expired_stopping",
                                    extra={"context": {"page": page, "collected": len(results)}})
                        raise TokenExpiredError(
                            f"Bidzaar token expired on page {page} after collecting {len(results)} tenders"
                        ) from e
                    raise

                items = data.get("items") or []
                if total_count is None:
                    total_count = data.get("totalCount", 0)
                    log.info("bidzaar_fetch_start",
                             extra={"context": {"total": total_count, "max_pages": self.MAX_PAGES}})
                if not items:
                    break

                for item in items:
                    dl = self._extract_deadline_from_raw(item)
                    if dl and dl < now:
                        skipped_streak += 1
                        continue
                    skipped_streak = 0
                    results.append(RawTender(platform="bidzaar", external_id=str(item["id"]), raw=dict(item)))

                if skipped_streak >= self.INCREMENTAL_SKIP_STREAK:
                    log.info("bidzaar_fetch_stopping_old",
                             extra={"context": {"page": page, "skipped_streak": skipped_streak}})
                    break
                if total_count and len(results) >= total_count:
                    break
                page += 1
                await asyncio.sleep(self._rate_limit)

        log.info("bidzaar_fetch_done", extra={"context": {"page": page, "fetched": len(results)}})

        if results:
            log.info("bidzaar_fetch_deadlines_start", extra={"context": {"count": len(results)}})
            await self._fetch_deadlines(results)
            log.info("bidzaar_fetch_deadlines_done", extra={"context": {"count": len(results)}})

        return results

    async def _fetch_deadlines(self, tenders: list[RawTender]) -> None:
        async with httpx.AsyncClient(headers=self._build_headers(), timeout=30.0) as client:
            for t in tenders:
                try:
                    r = await client.get(
                        f"https://bidzaar.com/api/process/light/procedures/read/{t.external_id}/main-view",
                    )
                    if r.status_code == 200:
                        data = r.json()
                        deadline = (data.get("parameters", {}) or {}).get("acceptanceEndDate")
                        if deadline:
                            t.raw["_deadline"] = deadline
                    await asyncio.sleep(self._rate_limit * 0.5)
                except Exception as e:
                    log.warning("bidzaar_deadline_fetch_failed",
                                extra={"context": {"id": t.external_id, "error": str(e)}})

    @staticmethod
    def _extract_deadline_from_raw(raw: dict) -> datetime | None:
        value = raw.get("_deadline") or raw.get("finishDate")
        if value:
            try:
                return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            except (ValueError, TypeError):
                pass
        return None

    async def _fetch_page(self, client: httpx.AsyncClient, page: int) -> dict:
        response = await client.get(LIST_URL, params={"paging.page": page, "paging.size": self._page_size})
        response.raise_for_status()
        return response.json()

    def _build_headers(self) -> dict[str, str]:
        headers: dict[str, str] = {
            "Authorization": f"Bearer {self._session.token}",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/145.0.7632.6 Safari/537.36",
            "Referer": "https://bidzaar.com/",
            "Origin": "https://bidzaar.com",
        }
        company_cookie = self._session.cookies.get("x-company-id", "")
        if "%3B" in company_cookie:
            company_id = company_cookie.split("%3B")[-1]
        elif company_cookie:
            company_id = company_cookie
        else:
            company_id = ""
        if company_id:
            headers["x-user-companyid"] = company_id
        return headers
