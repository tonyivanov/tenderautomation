import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock

from adapters.bidzaar.api_client import BidzaarApiClient
from core.models import PlatformDescriptor


def client() -> BidzaarApiClient:
    return BidzaarApiClient("integrator", PlatformDescriptor(
        platform_id="bidzaar", display_name="Bidzaar", base_url="https://example.test",
        auth_method="none", rate_limit_sec=0, extra={"page_size": 25}))


def test_incremental_boundary_expiry_and_unknown_deadline() -> None:
    subject = client()
    subject._fetch_page = AsyncMock(return_value={"items": [
        {"link": "https://bidzaar.com/process/light/new", "publishDate": "2026-01-11T00:00:00Z", "acceptanceEndDate": "2099-01-01T00:00:00Z"},
        {"link": "https://bidzaar.com/process/light/expired", "publishDate": "2026-01-11T00:00:00Z", "acceptanceEndDate": "2000-01-01T00:00:00"},
        {"link": "https://bidzaar.com/process/light/missing", "publishDate": "2026-01-11T00:00:00Z"},
        {"link": "https://bidzaar.com/process/light/old", "publishDate": "2026-01-09T00:00:00Z", "acceptanceEndDate": "2099-01-01T00:00:00Z"},
    ]})
    result = asyncio.run(subject.fetch_new(datetime(2026, 1, 10, tzinfo=timezone.utc)))
    assert [row.external_id for row in result] == ["new", "expired", "missing"]


def test_naive_datetimes_are_normalized_to_utc() -> None:
    value = BidzaarApiClient._as_utc(datetime(2026, 1, 1))
    assert value.tzinfo == timezone.utc
    assert BidzaarApiClient._as_utc(value) == value
