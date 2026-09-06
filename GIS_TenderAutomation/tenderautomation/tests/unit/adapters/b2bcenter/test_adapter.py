"""Tests for B2BCenterAdapter.map_to_tender — PBT: determinism, ID format."""
from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from core.models import RawTender
from adapters.b2bcenter.adapter import B2BCenterAdapter

_adapter = B2BCenterAdapter.__new__(B2BCenterAdapter)


def _make_raw(lot_id: str, title: str, buyer: str | None = None) -> RawTender:
    return RawTender(
        platform="b2bcenter",
        external_id=lot_id,
        raw={
            "lot_id": lot_id,
            "title": title,
            "buyer": buyer,
            "budget_raw": "500 000 руб.",
            "deadline_raw": "31.12.2026 23:59",
            "url": f"https://www.b2b-center.ru/market/{lot_id}/",
            "search_query": "DevOps",
        },
    )


class TestMapToTender:
    def test_id_format(self):
        raw = _make_raw("12345", "DevOps services")
        tender = _adapter.map_to_tender(raw, None)
        assert tender.id == "b2bcenter_12345"
        assert tender.platform == "b2bcenter"
        assert tender.external_id == "12345"

    def test_required_fields_populated(self):
        raw = _make_raw("99", "Test Tender")
        tender = _adapter.map_to_tender(raw, None)
        assert tender.title
        assert tender.url
        assert tender.id

    def test_empty_title_raises(self):
        raw = _make_raw("1", "")
        with pytest.raises(ValueError):
            _adapter.map_to_tender(raw, None)

    @given(
        lot_id=st.from_regex(r"[1-9]\d{3,8}", fullmatch=True),
        title=st.text(min_size=3, max_size=200),
    )
    def test_deterministic(self, lot_id, title):
        raw = _make_raw(lot_id, title)
        t1 = _adapter.map_to_tender(raw, None)
        t2 = _adapter.map_to_tender(raw, None)
        assert t1.id == t2.id
        assert t1.title == t2.title
        assert t1.content_hash == t2.content_hash
