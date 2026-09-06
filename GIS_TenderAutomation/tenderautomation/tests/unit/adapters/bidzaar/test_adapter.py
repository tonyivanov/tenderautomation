"""Tests for BidzaarAdapter.map_to_tender — PBT: determinism, ID format."""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from hypothesis import given
from hypothesis import strategies as st

from core.models import AuthSession, DeadlineExtractionState, RawTender
from adapters.bidzaar import adapter as adapter_module
from adapters.bidzaar.adapter import BidzaarAdapter
from adapters.bidzaar.urls import canonical_bidzaar_url

_adapter = BidzaarAdapter.__new__(BidzaarAdapter)


def _make_raw(tender_id: int, name: str, price: float | None = 500000.0) -> RawTender:
    return RawTender(
        platform="bidzaar",
        external_id=str(tender_id),
        raw={
            "id": tender_id,
            "name": name,
            "organizationName": "ООО Тест",
            "startPrice": price,
            "finishDate": "2026-12-31T23:59:00Z",
            "startDate": "2026-06-01T10:00:00Z",
            "description": "Test description",
        },
    )


class TestMapToTender:
    def test_id_format(self):
        raw = _make_raw(12345, "Kubernetes infrastructure")
        tender = _adapter.map_to_tender(raw, None)
        assert tender.id == "bidzaar_12345"
        assert tender.platform == "bidzaar"
        assert tender.external_id == "12345"

    def test_url_format(self):
        raw = _make_raw(42, "Test")
        tender = _adapter.map_to_tender(raw, None)
        assert tender.url == "https://bidzaar.com/app/process/light/42"

    def test_api_link_host_and_path_are_ignored(self):
        raw = _make_raw(42, "Test")
        raw.raw["link"] = "https://evil.example/steal?token=secret"
        assert _adapter.map_to_tender(raw, None).url.endswith("/42")

    def test_required_fields_populated(self):
        raw = _make_raw(1, "DevOps platform")
        tender = _adapter.map_to_tender(raw, None)
        assert tender.title
        assert tender.url
        assert tender.id

    def test_empty_name_raises(self):
        raw = _make_raw(1, "")
        with pytest.raises(ValueError):
            _adapter.map_to_tender(raw, None)

    def test_budget_parsed(self):
        raw = _make_raw(1, "Test", price=1500000.0)
        tender = _adapter.map_to_tender(raw, None)
        from decimal import Decimal
        assert tender.budget == Decimal("1500000.0")

    def test_none_price_allowed(self):
        raw = _make_raw(1, "Test", price=None)
        tender = _adapter.map_to_tender(raw, None)
        assert tender.budget is None

    @given(
        tender_id=st.integers(min_value=1, max_value=10_000_000),
        name=st.text(min_size=3, max_size=200),
    )
    def test_deterministic(self, tender_id, name):
        raw = _make_raw(tender_id, name)
        t1 = _adapter.map_to_tender(raw, None)
        t2 = _adapter.map_to_tender(raw, None)
        assert t1.id == t2.id
        assert t1.title == t2.title
        assert t1.content_hash == t2.content_hash

    @given(tender_id=st.integers(min_value=1, max_value=10_000_000))
    def test_id_always_prefixed(self, tender_id):
        raw = _make_raw(tender_id, "Test tender")
        tender = _adapter.map_to_tender(raw, None)
        assert tender.id.startswith("bidzaar_")


@given(st.from_regex(r"[A-Za-z0-9._~-]{1,40}", fullmatch=True))
def test_canonical_url_is_idempotent(external_id: str) -> None:
    once = canonical_bidzaar_url(external_id)
    assert canonical_bidzaar_url(once) == once


@pytest.mark.parametrize("external_id", ["../secret", "a/b", "", "x?token=secret"])
def test_invalid_external_id_is_rejected(external_id: str) -> None:
    with pytest.raises(ValueError, match="Invalid Bidzaar"):
        canonical_bidzaar_url(external_id)


def test_detail_404_returns_safe_category(monkeypatch) -> None:
    response = SimpleNamespace(status_code=404, text="", raise_for_status=lambda: None)

    class FakeClient:
        def __init__(self, **kwargs) -> None:
            self.kwargs = kwargs

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def get(self, url: str):
            assert url == "https://bidzaar.com/app/process/light/abc"
            return response

    monkeypatch.setattr(adapter_module.httpx, "AsyncClient", FakeClient)
    outcome = asyncio.run(
        _adapter._fetch_detail_outcome(AuthSession(platform="bidzaar"), "abc")
    )
    assert outcome.state is DeadlineExtractionState.EXTERNAL_FAILURE
    assert outcome.error_category is not None
    assert outcome.error_category.value == "not_found"


def test_detail_success_extracts_explicit_label(monkeypatch) -> None:
    response = SimpleNamespace(
        status_code=200,
        text="<p>Приём предложений до: 25.07.2026 18:00</p>",
        raise_for_status=lambda: None,
    )

    class FakeClient:
        def __init__(self, **kwargs) -> None:
            self.kwargs = kwargs

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def get(self, url: str):
            return response

    monkeypatch.setattr(adapter_module.httpx, "AsyncClient", FakeClient)
    outcome = asyncio.run(
        _adapter._fetch_detail_outcome(AuthSession(platform="bidzaar"), "abc")
    )
    assert outcome.state is DeadlineExtractionState.RESOLVED
    assert outcome.deadline is not None
    assert outcome.deadline.source.value == "detail"
