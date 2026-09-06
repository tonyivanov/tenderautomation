"""PBT tests for B2B-Center parsers — parse_price and parse_deadline invariants."""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st

from adapters.b2bcenter.parsers import parse_deadline, parse_detail_deadline, parse_price
from core.models import DeadlineExtractionState, DeadlineLabelKind


class TestParsePrice:
    @given(
        rub=st.decimals(min_value=Decimal("1"), max_value=Decimal("1000000000"),
                         allow_nan=False, allow_infinity=False).map(lambda d: round(d, 2))
    )
    def test_valid_price_always_nonnegative(self, rub):
        text = f"{rub:,.2f} руб.".replace(",", " ")
        result = parse_price(text)
        if result is not None:
            assert result >= 0

    def test_none_input_returns_none(self):
        assert parse_price(None) is None

    def test_empty_string_returns_none(self):
        assert parse_price("") is None

    def test_dogovor_returns_none(self):
        assert parse_price("договорная") is None
        assert parse_price("по договору") is None

    def test_valid_rub_parsed(self):
        assert parse_price("1 500 000 руб.") == Decimal("1500000")

    def test_valid_with_decimals(self):
        result = parse_price("750 000.50 руб.")
        assert result == Decimal("750000.50")

    def test_zero_returns_none(self):
        assert parse_price("0") is None

    @given(st.text(max_size=50))
    def test_never_raises(self, text):
        # parse_price should never raise, only return None or Decimal
        result = parse_price(text)
        assert result is None or (isinstance(result, Decimal) and result > 0)


class TestParseDeadline:
    def test_full_format_parsed(self):
        result = parse_deadline("15.07.2026 23:59")
        assert result == datetime(2026, 7, 15, 20, 59, tzinfo=timezone.utc)

    def test_date_only_parsed(self):
        result = parse_deadline("15.07.2026")
        assert result is not None
        assert result.year == 2026
        assert result.month == 7
        assert result.day == 15

    def test_moscow_timezone_applied(self):
        result = parse_deadline("01.01.2026 00:00")
        assert result is not None
        assert result == datetime(2025, 12, 31, 21, tzinfo=timezone.utc)

    def test_none_returns_none(self):
        assert parse_deadline(None) is None

    def test_empty_returns_none(self):
        assert parse_deadline("") is None

    def test_invalid_format_returns_none(self):
        assert parse_deadline("not-a-date") is None

    @given(st.text(max_size=30))
    def test_never_raises(self, text):
        result = parse_deadline(text)
        assert result is None or isinstance(result, datetime)


class TestDetailDeadline:
    def test_acceptance_end_is_preferred_to_trading_date(self):
        html = """
        <dl>
          <dt>Дата торгов</dt><dd>28.07.2026 10:00</dd>
          <dt>Окончание приёма заявок</dt><dd>25.07.2026 18:00</dd>
        </dl>
        """
        outcome = parse_detail_deadline(html)
        assert outcome.state is DeadlineExtractionState.RESOLVED
        assert outcome.deadline is not None
        assert outcome.deadline.label_kind is DeadlineLabelKind.ACCEPTANCE_END

    def test_unlabelled_date_is_ignored(self):
        outcome = parse_detail_deadline("<p>25.07.2026 18:00</p>")
        assert outcome.state is DeadlineExtractionState.MISSING

    def test_conflicting_acceptance_dates_are_ambiguous(self):
        html = """
        <p>Окончание приёма заявок: 25.07.2026 18:00</p>
        <p>Deadline: 26.07.2026 18:00</p>
        """
        assert parse_detail_deadline(html).state is DeadlineExtractionState.AMBIGUOUS

    def test_missing_acceptance_value_does_not_steal_trading_date(self):
        html = """
        <p>Окончание приёма заявок</p>
        <p>Дата торгов: 26.07.2026 18:00</p>
        """
        outcome = parse_detail_deadline(html)
        assert outcome.state is DeadlineExtractionState.RESOLVED
        assert outcome.deadline is not None
        assert outcome.deadline.label_kind is DeadlineLabelKind.TRADING_DATE
