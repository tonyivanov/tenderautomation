import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock

from adapters.bidzaar.adapter import BidzaarAdapter
from adapters.bidzaar.api_client import BidzaarApiClient
from core.models import PlatformDescriptor, RawTender


def _descriptor(page_size: int = 50) -> PlatformDescriptor:
    return PlatformDescriptor(
        platform_id="bidzaar",
        display_name="Bidzaar",
        base_url="https://bidzaar.com",
        auth_method="none",
        rate_limit_sec=0,
        extra={"page_size": page_size},
    )


def _integrator_item(tender_id: str = "a1b2c3") -> dict:
    return {
        "name": "Infrastructure audit",
        "publisherName": "Test publisher",
        "price": 1500000.0,
        "acceptanceEndDate": "2099-12-31T23:59:00Z",
        "publishDate": "2026-07-17T10:00:00Z",
        "description": "Test description",
        "link": f"https://bidzaar.com/process/light/{tender_id}",
    }


def test_integrator_fetch_is_async_and_deduplicates_links() -> None:
    client = BidzaarApiClient("integrator", _descriptor(page_size=3))
    item = _integrator_item()
    client._fetch_page = AsyncMock(return_value={"items": [item, item], "pageSize": 3})

    result = asyncio.run(client.fetch_new(datetime(2026, 7, 10, tzinfo=timezone.utc)))

    assert [row.external_id for row in result] == ["a1b2c3"]
    assert client._fetch_page.await_count == 1


def test_integrator_from_date_is_clamped_to_supported_window() -> None:
    now = datetime(2026, 7, 17, 12, tzinfo=timezone.utc)

    assert BidzaarApiClient._clamp_from_date(None, now=now) == "2026-07-04"
    assert BidzaarApiClient._clamp_from_date(
        datetime(2026, 7, 16, tzinfo=timezone.utc), now=now
    ) == "2026-07-16"
    assert BidzaarApiClient._clamp_from_date(
        datetime(2026, 7, 16), now=now
    ) == "2026-07-16"


def test_integrator_schema_maps_to_tender() -> None:
    raw = RawTender(platform="bidzaar", external_id="a1b2c3", raw=_integrator_item())

    tender = BidzaarAdapter.__new__(BidzaarAdapter).map_to_tender(raw, _descriptor())

    assert tender.id == "bidzaar_a1b2c3"
    assert tender.buyer == "Test publisher"
    assert str(tender.budget) == "1500000.0"
    assert tender.url.endswith("/a1b2c3")
