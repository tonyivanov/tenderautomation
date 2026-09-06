import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest

from adapters.b2bcenter.parsers import B2BCenterRawRow
from adapters.b2bcenter.scraper import B2BCenterScraper
from core.models import PlatformDescriptor, RawTender


def _descriptor(modes: list[str]) -> PlatformDescriptor:
    return PlatformDescriptor(
        platform_id="b2bcenter",
        display_name="B2B-Center",
        base_url="https://www.b2b-center.ru",
        auth_method="none",
        rate_limit_sec=0,
        extra={"fetch_modes": modes, "page_size": 20},
    )


def _row(
    tender_id: str,
    source: str,
    *,
    deadline_raw: str | None = None,
    deadline_source: str | None = None,
) -> RawTender:
    return RawTender(
        platform="b2bcenter",
        external_id=tender_id,
        raw={
            "search_query": source,
            "deadline_raw": deadline_raw,
            "deadline_source": deadline_source,
        },
    )


def test_both_modes_are_combined_and_deduplicated() -> None:
    subject = B2BCenterScraper(_descriptor(["endpoint", "playwright"]), Path("unused"))
    subject._fetch_endpoint = AsyncMock(return_value=[_row("one", "endpoint")])
    subject._fetch_playwright = AsyncMock(
        return_value=[_row("one", "playwright"), _row("two", "playwright")]
    )

    result = asyncio.run(subject.fetch_new())

    assert [row.external_id for row in result] == ["one", "two"]
    subject._fetch_endpoint.assert_awaited_once_with(None)
    subject._fetch_playwright.assert_awaited_once_with(None)


def test_playwright_still_runs_when_endpoint_fails() -> None:
    subject = B2BCenterScraper(_descriptor(["endpoint", "playwright"]), Path("unused"))
    subject._fetch_endpoint = AsyncMock(side_effect=RuntimeError("endpoint unavailable"))
    subject._fetch_playwright = AsyncMock(return_value=[_row("two", "playwright")])

    result = asyncio.run(subject.fetch_new())

    assert [row.external_id for row in result] == ["two"]


def test_endpoint_only_mode_does_not_start_playwright() -> None:
    subject = B2BCenterScraper(_descriptor(["endpoint"]), Path("unused"))
    subject._fetch_endpoint = AsyncMock(return_value=[])
    subject._fetch_playwright = AsyncMock()

    assert asyncio.run(subject.fetch_new()) == []
    subject._fetch_playwright.assert_not_awaited()


def test_unknown_fetch_mode_is_rejected() -> None:
    with pytest.raises(ValueError, match="Unsupported B2B-Center fetch modes"):
        B2BCenterScraper(_descriptor(["ftp"]), Path("unused"))


def test_dedup_merge_keeps_best_deadline_and_all_queries() -> None:
    missing = _row("one", "endpoint")
    detailed = _row(
        "one", "playwright", deadline_raw="2026-07-25T15:00:00Z", deadline_source="detail"
    )
    listing = _row(
        "one", "structured", deadline_raw="2026-07-25T16:00:00Z", deadline_source="listing"
    )
    merged = B2BCenterScraper._deduplicate([missing, detailed, listing])[0]
    assert merged.raw["deadline_source"] == "listing"
    assert merged.raw["deadline_raw"] == "2026-07-25T16:00:00Z"
    assert merged.raw["search_queries"] == ["endpoint", "playwright", "structured"]


def test_endpoint_detail_failure_preserves_row(monkeypatch) -> None:
    subject = B2BCenterScraper(_descriptor(["endpoint"]), Path("unused"))
    row = B2BCenterRawRow(
        "1", "Tender", None, None, None,
        "https://www.b2b-center.ru/market/view.html?id=1", "endpoint"
    )
    client = AsyncMock()
    client.get.side_effect = httpx.TimeoutException("timeout")
    result = asyncio.run(subject._row_to_raw_endpoint(row, client))
    assert result.raw["deadline_source"] == "unresolved"
    assert result.raw["deadline_error_category"] == "timeout"


def test_endpoint_detail_success_uses_same_client() -> None:
    subject = B2BCenterScraper(_descriptor(["endpoint"]), Path("unused"))
    row = B2BCenterRawRow(
        "1", "Tender", None, None, None,
        "https://www.b2b-center.ru/market/view.html?id=1", "endpoint"
    )
    response = SimpleNamespace(
        status_code=200,
        text="<p>Окончание приёма заявок: 25.07.2026 18:00</p>",
        raise_for_status=lambda: None,
    )
    client = AsyncMock()
    client.get.return_value = response
    result = asyncio.run(subject._row_to_raw_endpoint(row, client))
    assert result.raw["deadline_source"] == "detail"
    assert result.raw["deadline_extraction_state"] == "resolved"
    client.get.assert_awaited_once_with(row.url)


def test_endpoint_captcha_is_safe_unresolved() -> None:
    subject = B2BCenterScraper(_descriptor(["endpoint"]), Path("unused"))
    row = B2BCenterRawRow(
        "1", "Tender", None, None, None,
        "https://www.b2b-center.ru/market/view.html?id=1", "endpoint"
    )
    response = SimpleNamespace(
        status_code=200,
        text="<html><body>captcha</body></html>",
        raise_for_status=lambda: None,
    )
    client = AsyncMock()
    client.get.return_value = response
    result = asyncio.run(subject._row_to_raw_endpoint(row, client))
    assert result.raw["deadline_error_category"] == "captcha"


def test_playwright_detail_fallback_reuses_detail_page() -> None:
    subject = B2BCenterScraper(_descriptor(["playwright"]), Path("unused"))
    row = B2BCenterRawRow(
        "1", "Tender", None, None, None,
        "https://www.b2b-center.ru/market/view.html?id=1", "query"
    )
    detail_page = AsyncMock()
    detail_page.goto.return_value = SimpleNamespace(status=200)
    detail_page.content.return_value = (
        "<p>Дата торгов: 29.07.2026 11:00</p>"
    )
    result = asyncio.run(subject._row_to_raw_playwright(row, detail_page))
    assert result.raw["deadline_source"] == "detail"
    assert result.raw["deadline_label_kind"] == "trading_date"
    detail_page.goto.assert_awaited_once_with(
        row.url, wait_until="domcontentloaded", timeout=30000
    )


def test_playwright_404_is_safe_unresolved() -> None:
    subject = B2BCenterScraper(_descriptor(["playwright"]), Path("unused"))
    row = B2BCenterRawRow(
        "1", "Tender", None, None, None,
        "https://www.b2b-center.ru/market/view.html?id=1", "query"
    )
    detail_page = AsyncMock()
    detail_page.goto.return_value = SimpleNamespace(status=404)
    result = asyncio.run(subject._row_to_raw_playwright(row, detail_page))
    assert result.raw["deadline_error_category"] == "not_found"
    detail_page.content.assert_not_awaited()


def test_valid_listing_deadline_skips_detail_page() -> None:
    subject = B2BCenterScraper(_descriptor(["playwright"]), Path("unused"))
    row = B2BCenterRawRow(
        "1", "Tender", None, None, "25.07.2026 18:00",
        "https://www.b2b-center.ru/market/view.html?id=1", "query"
    )
    detail_page = AsyncMock()
    result = asyncio.run(subject._row_to_raw_playwright(row, detail_page))
    assert result.raw["deadline_source"] == "listing"
    detail_page.goto.assert_not_awaited()


def test_playwright_resources_are_closed(monkeypatch) -> None:
    subject = B2BCenterScraper(_descriptor(["playwright"]), Path("unused"))
    subject._load_queries = lambda: ["cloud"]
    subject._fetch_query = AsyncMock(return_value=[])
    subject._antibot_sleep = AsyncMock()

    search_page = AsyncMock()
    detail_page = AsyncMock()
    context = AsyncMock()
    context.new_page.side_effect = [search_page, detail_page]
    browser = AsyncMock()
    browser.new_context.return_value = context
    chromium = SimpleNamespace(launch=AsyncMock(return_value=browser))
    pw = SimpleNamespace(chromium=chromium, stop=AsyncMock())
    starter = SimpleNamespace(start=AsyncMock(return_value=pw))
    monkeypatch.setattr(
        "playwright.async_api.async_playwright", lambda: starter
    )

    assert asyncio.run(subject._fetch_playwright(None)) == []
    detail_page.close.assert_awaited_once()
    context.close.assert_awaited_once()
    browser.close.assert_awaited_once()
    pw.stop.assert_awaited_once()
