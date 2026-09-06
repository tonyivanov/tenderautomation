from datetime import datetime, timezone

import pytest

from core.models import (
    DeadlineCandidate,
    DeadlineErrorCategory,
    DeadlineExtractionOutcome,
    DeadlineExtractionState,
    DeadlineSource,
    NormalizedDeadline,
    ReconciliationCommand,
    ReconciliationResult,
)


def test_normalized_deadline_rejects_naive_value() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        NormalizedDeadline(datetime(2026, 1, 1), DeadlineSource.API)


def test_external_failure_contains_only_safe_category() -> None:
    outcome = DeadlineExtractionOutcome(
        None,
        DeadlineExtractionState.EXTERNAL_FAILURE,
        DeadlineErrorCategory.TIMEOUT,
    )
    assert "secret" not in repr(outcome).lower()
    assert outcome.error_category is DeadlineErrorCategory.TIMEOUT


@pytest.mark.parametrize("batch_size", [0, 201, -1, True])
def test_reconciliation_command_rejects_out_of_range(batch_size: int) -> None:
    with pytest.raises(ValueError, match="between 1 and 200"):
        ReconciliationCommand(batch_size=batch_size)


def test_reconciliation_result_rejects_negative_counters() -> None:
    with pytest.raises(ValueError, match="nonnegative"):
        ReconciliationResult(failed=-1)


def test_candidate_repr_does_not_expose_raw_text() -> None:
    candidate = DeadlineCandidate(
        raw_text="token=top-secret",
        source=DeadlineSource.DETAIL,
        label_kind=None,
        priority=1,
        parsed_value=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    assert "top-secret" not in repr(candidate)
