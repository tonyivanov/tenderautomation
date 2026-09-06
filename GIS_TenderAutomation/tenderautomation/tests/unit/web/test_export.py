"""PBT tests for ExportService — JSONL round-trip."""
from __future__ import annotations

import json
from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st

from core.models.tender import TenderModel, TenderStatus
from web.services.export import ExportService


def _make_tender(tid: str, title: str) -> TenderModel:
    return TenderModel(
        id=f"bidzaar_{tid}",
        platform="bidzaar",
        external_id=tid,
        title=title,
        url=f"https://bidzaar.com/requests/public/{tid}",
        prefilter_score=50,
        qualification_tier="qualified",
        status=TenderStatus.QUALIFIED,
    )


class TestJsonlRoundTrip:
    @given(
        tid=st.from_regex(r"[1-9]\d{3,6}", fullmatch=True),
        title=st.text(min_size=3, max_size=100),
    )
    def test_jsonl_line_is_valid_json(self, tid, title):
        tender = _make_tender(tid, title)
        line = json.dumps(tender.to_jsonl_dict(), ensure_ascii=False)
        parsed = json.loads(line)
        assert parsed["id"] == tender.id
        assert parsed["platform"] == "bidzaar"
        assert parsed["title"] == title

    def test_multiple_tenders_one_per_line(self):
        tenders = [_make_tender(str(i), f"Tender {i}") for i in range(1, 6)]
        from unittest.mock import MagicMock
        svc = ExportService.__new__(ExportService)
        jsonl = ExportService._build_jsonl(tenders)
        lines = [l for l in jsonl.strip().split("\n") if l]
        assert len(lines) == 5
        for line in lines:
            parsed = json.loads(line)
            assert "id" in parsed
            assert "title" in parsed

    def test_empty_list_produces_empty_jsonl(self):
        jsonl = ExportService._build_jsonl([])
        assert jsonl == ""
