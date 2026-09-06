"""Tests for JSONL serialization — PBT: round-trip TenderModel → JSONL → dict."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st

from core.models.tender import TenderModel, TenderStatus


def _tender_strategy():
    return st.builds(
        TenderModel,
        id=st.just("bidzaar_42"),
        platform=st.just("bidzaar"),
        external_id=st.just("42"),
        title=st.text(min_size=1, max_size=200, alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd", "Zs"))),
        buyer=st.one_of(st.none(), st.text(max_size=100)),
        budget=st.one_of(st.none(), st.decimals(min_value=0, max_value=1_000_000_000, allow_nan=False, allow_infinity=False).map(lambda d: round(d, 2))),
        deadline=st.one_of(st.none(), st.datetimes(timezones=st.just(timezone.utc))),
        description=st.one_of(st.none(), st.text(max_size=500)),
        url=st.just("https://bidzaar.com/tender/42"),
        prefilter_score=st.integers(min_value=0, max_value=500),
        qualification_tier=st.one_of(st.none(), st.just("qualified"), st.just("filtered")),
        matched_keywords=st.lists(st.text(min_size=1, max_size=30), max_size=10),
        status=st.just(TenderStatus.QUALIFIED),
    )


class TestJsonlRoundTrip:
    @given(_tender_strategy())
    def test_serializes_to_valid_json(self, tender: TenderModel):
        d = tender.to_jsonl_dict()
        line = json.dumps(d, ensure_ascii=False)
        parsed = json.loads(line)
        assert parsed["id"] == tender.id
        assert parsed["platform"] == tender.platform

    @given(_tender_strategy())
    def test_budget_is_string_or_none(self, tender: TenderModel):
        d = tender.to_jsonl_dict()
        if d["budget"] is not None:
            assert isinstance(d["budget"], str)

    @given(_tender_strategy())
    def test_required_fields_present(self, tender: TenderModel):
        d = tender.to_jsonl_dict()
        required = {"id", "platform", "title", "url", "prefilter_score",
                    "qualification_tier", "matched_keywords", "exported_at"}
        assert required.issubset(d.keys())

    @given(_tender_strategy())
    def test_exported_at_is_iso8601(self, tender: TenderModel):
        d = tender.to_jsonl_dict()
        exported_at = d["exported_at"]
        assert isinstance(exported_at, str)
        # Should parse without error
        datetime.fromisoformat(exported_at)

    def test_none_budget_serializes_as_null(self):
        tender = TenderModel(
            id="b2bcenter_1", platform="b2bcenter", external_id="1",
            title="Test", url="https://example.com", budget=None
        )
        d = tender.to_jsonl_dict()
        line = json.dumps(d)
        parsed = json.loads(line)
        assert parsed["budget"] is None
