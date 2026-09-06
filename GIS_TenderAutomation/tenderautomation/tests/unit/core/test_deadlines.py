from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest
from hypothesis import given
from hypothesis import strategies as st

from core.models import (
    DeadlineExtractionState,
    DeadlineLabelKind,
    DeadlineSource,
)
from core.services.deadlines import (
    is_expired,
    make_candidate,
    normalize_deadline,
    parse_deadline_value,
    provenance,
    resolve_deadline_candidates,
)


@given(st.text(max_size=120))
def test_arbitrary_deadline_text_never_raises(text: str) -> None:
    result = parse_deadline_value(text)
    assert result is None or result[0].tzinfo is not None


@given(st.dates(min_value=datetime(2000, 1, 1).date(), max_value=datetime(2099, 12, 31).date()))
def test_date_only_is_platform_local_end_of_day(value) -> None:
    parsed = parse_deadline_value(value.strftime("%d.%m.%Y"))
    assert parsed is not None
    utc_value, date_only = parsed
    assert date_only is True
    assert utc_value.astimezone(ZoneInfo("Europe/Moscow")).time() == datetime.strptime(
        "23:59:59", "%H:%M:%S"
    ).time()


def test_explicit_offset_takes_precedence_over_platform_timezone() -> None:
    parsed = parse_deadline_value("2026-07-22T12:00:00+05:00")
    assert parsed == (datetime(2026, 7, 22, 7, tzinfo=timezone.utc), False)


def test_acceptance_end_precedes_trading_date() -> None:
    trading = make_candidate(
        "25.07.2026",
        source=DeadlineSource.DETAIL,
        label_kind=DeadlineLabelKind.TRADING_DATE,
        priority=2,
    )
    acceptance = make_candidate(
        "24.07.2026 12:00",
        source=DeadlineSource.DETAIL,
        label_kind=DeadlineLabelKind.ACCEPTANCE_END,
        priority=1,
    )
    outcome = resolve_deadline_candidates([trading, acceptance])
    assert outcome.state is DeadlineExtractionState.RESOLVED
    assert outcome.deadline is not None
    assert outcome.deadline.label_kind is DeadlineLabelKind.ACCEPTANCE_END


def test_same_priority_conflict_is_ambiguous() -> None:
    candidates = [
        make_candidate(
            value,
            source=DeadlineSource.DETAIL,
            label_kind=DeadlineLabelKind.ACCEPTANCE_END,
            priority=1,
        )
        for value in ("24.07.2026", "25.07.2026")
    ]
    assert resolve_deadline_candidates(candidates).state is DeadlineExtractionState.AMBIGUOUS


def test_unlabelled_candidate_is_not_inferred() -> None:
    candidate = make_candidate(
        "24.07.2026",
        source=DeadlineSource.DETAIL,
        label_kind=None,
        priority=1,
    )
    assert resolve_deadline_candidates([candidate]).state is DeadlineExtractionState.INVALID


@given(
    deadline=st.datetimes(
        min_value=datetime(2000, 1, 1),
        max_value=datetime(2099, 12, 31),
        timezones=st.just(timezone.utc),
    ),
    delta=st.timedeltas(min_value=timedelta(microseconds=1), max_value=timedelta(days=365)),
)
def test_expiry_is_monotonic(deadline: datetime, delta: timedelta) -> None:
    now = deadline + timedelta(microseconds=1)
    assert is_expired(deadline, now)
    assert is_expired(deadline, now + delta)


def test_expiry_equality_and_unknown_are_not_expired() -> None:
    value = datetime(2026, 7, 22, tzinfo=timezone.utc)
    assert not is_expired(value, value)
    assert not is_expired(None, value)
    assert not is_expired(datetime(2026, 7, 21), value)


def test_normalization_and_provenance_are_stable() -> None:
    normalized = normalize_deadline(
        "2026-07-22T12:00:00Z", source=DeadlineSource.API
    )
    assert normalized is not None
    again = normalize_deadline(normalized.value.isoformat(), source=DeadlineSource.API)
    assert again is not None and again.value == normalized.value
    outcome = resolve_deadline_candidates(
        [
            make_candidate(
                normalized.value.isoformat(),
                source=DeadlineSource.API,
                label_kind=DeadlineLabelKind.ACCEPTANCE_END,
                priority=1,
            )
        ]
    )
    assert provenance(outcome)["deadline_source"] == "api"


@pytest.mark.parametrize(
    "value",
    ["31.02.2026", "publication 22.07.2026", "", "2026/07/22"],
)
def test_invalid_or_unlabelled_formats_are_unresolved(value: str) -> None:
    assert parse_deadline_value(value) is None
