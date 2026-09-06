"""Tests for content_hash — PBT: determinism and sensitivity."""
from decimal import Decimal
from datetime import datetime, timezone

import pytest
from hypothesis import given, settings as h_settings
from hypothesis import strategies as st

from core.models.tender import compute_content_hash


def _hash(title="T", buyer=None, budget=None, deadline=None, description=None):
    return compute_content_hash(title, buyer, budget, deadline, description)


class TestContentHashDeterminism:
    @given(
        title=st.text(min_size=1, max_size=200),
        buyer=st.one_of(st.none(), st.text(max_size=100)),
        description=st.one_of(st.none(), st.text(max_size=500)),
    )
    def test_same_inputs_same_hash(self, title, buyer, description):
        h1 = _hash(title=title, buyer=buyer, description=description)
        h2 = _hash(title=title, buyer=buyer, description=description)
        assert h1 == h2

    def test_hash_is_64_hex_chars(self):
        h = _hash("test title")
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)

    def test_case_insensitive(self):
        h1 = _hash("Cloud Migration")
        h2 = _hash("cloud migration")
        assert h1 == h2

    def test_whitespace_stripped(self):
        h1 = _hash("  Cloud Migration  ")
        h2 = _hash("Cloud Migration")
        assert h1 == h2


class TestContentHashSensitivity:
    @given(
        title_a=st.text(min_size=1, max_size=100),
        title_b=st.text(min_size=1, max_size=100),
    )
    def test_different_titles_different_hashes(self, title_a, title_b):
        if title_a.strip().lower() != title_b.strip().lower():
            assert _hash(title=title_a) != _hash(title=title_b)

    def test_none_vs_value_differs(self):
        assert _hash(buyer=None) != _hash(buyer="ООО Тест")

    def test_budget_precision(self):
        h1 = _hash(budget=Decimal("100.00"))
        h2 = _hash(budget=Decimal("100.01"))
        assert h1 != h2
