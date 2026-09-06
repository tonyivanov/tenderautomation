from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from core.models import (
    InspectionApplyStatus,
    InspectionErrorCategory,
    ProcedureState,
    TenderInspectionResult,
    TenderStatus,
)
from core.orm import TenderORM
from core.repositories.tender import TenderRepository


NOW = datetime(2026, 7, 23, tzinfo=timezone.utc)


def _row(tender_factory) -> TenderORM:
    tender = tender_factory(status=TenderStatus.DEFERRED, qualification_tier="qualified")
    return TenderORM(
        **{
            **tender.model_dump(exclude={
                "status", "procedure_state", "procedure_source", "procedure_error_category"
            }),
            "status": tender.status.value,
            "procedure_state": tender.procedure_state.value,
            "procedure_source": None,
            "procedure_error_category": None,
        }
    )


def _session(monkeypatch, row):
    session = MagicMock()
    session.get.return_value = row
    context = MagicMock()
    context.__enter__.return_value = session
    context.__exit__.return_value = False
    monkeypatch.setattr("core.repositories.tender.SessionLocal", lambda: context)
    return session


def test_export_limit_is_strict() -> None:
    with pytest.raises(ValueError):
        TenderRepository().get_export_candidates(limit=51)


def test_verified_apply_preserves_workflow_and_qualification(monkeypatch, tender_factory) -> None:
    row = _row(tender_factory)
    session = _session(monkeypatch, row)
    inspection = TenderInspectionResult(
        tender_id=row.id,
        state=ProcedureState.ACTIVE,
        verified=True,
        attempted_at=NOW,
        buyer=None,
        description="Enriched",
    )

    result = TenderRepository().apply_inspection(inspection)

    assert result.status is InspectionApplyStatus.APPLIED
    assert row.status == TenderStatus.DEFERRED.value
    assert row.qualification_tier == "qualified"
    assert row.buyer == "Test buyer"
    assert row.description == "Enriched"
    session.commit.assert_called_once()


def test_old_result_is_stale_and_failure_cannot_erase_verified_state(
    monkeypatch, tender_factory
) -> None:
    row = _row(tender_factory)
    row.procedure_state = ProcedureState.ACTIVE.value
    row.procedure_checked_at = NOW
    row.procedure_last_attempt_at = NOW
    _session(monkeypatch, row)
    failure = TenderInspectionResult(
        tender_id=row.id,
        attempted_at=NOW - timedelta(seconds=1),
        error_category=InspectionErrorCategory.NETWORK,
    )

    result = TenderRepository().apply_inspection(failure)

    assert result.status is InspectionApplyStatus.STALE
    assert row.procedure_state == ProcedureState.ACTIVE.value


def test_equal_timestamp_mismatch_is_conflict(monkeypatch, tender_factory) -> None:
    row = _row(tender_factory)
    row.procedure_last_attempt_at = NOW
    row.procedure_checked_at = NOW
    row.procedure_state = ProcedureState.CLOSED.value
    _session(monkeypatch, row)
    result = TenderRepository().apply_inspection(
        TenderInspectionResult(
            tender_id=row.id,
            state=ProcedureState.ACTIVE,
            verified=True,
            attempted_at=NOW,
        )
    )
    assert result.status is InspectionApplyStatus.CONFLICT


def test_missing_row_has_detached_missing_outcome(monkeypatch) -> None:
    _session(monkeypatch, None)
    result = TenderRepository().apply_inspection(
        TenderInspectionResult(tender_id="missing", attempted_at=NOW)
    )
    assert result.status is InspectionApplyStatus.MISSING
