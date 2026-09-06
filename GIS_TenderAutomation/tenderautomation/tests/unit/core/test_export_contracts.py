from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from core.models import (
    ExportRequest,
    InspectionErrorCategory,
    ProcedureState,
    TenderInspectionResult,
    TenderModel,
)


NOW = datetime(2026, 7, 23, tzinfo=timezone.utc)


def test_tender_procedure_defaults_do_not_change_workflow_status() -> None:
    tender = TenderModel(
        id="bidzaar_1",
        platform="bidzaar",
        external_id="1",
        title="Example",
        url="https://example.test/1",
    )

    assert tender.procedure_state is ProcedureState.UNKNOWN
    assert tender.status.value == "pending"
    assert tender.procedure_checked_at is None


def test_export_request_stably_deduplicates_ids() -> None:
    request = ExportRequest(
        tender_ids=("a", "b", "a", " b "), requested_at=NOW
    )

    assert request.tender_ids == ("a", "b")


@pytest.mark.parametrize("field", ["requested_at", "attempted_at"])
def test_export_timestamps_must_be_timezone_aware(field: str) -> None:
    with pytest.raises(ValidationError):
        if field == "requested_at":
            ExportRequest(requested_at=datetime(2026, 7, 23))
        else:
            TenderInspectionResult(
                tender_id="x", attempted_at=datetime(2026, 7, 23)
            )


def test_verified_result_rejects_error_and_unsafe_provenance() -> None:
    with pytest.raises(ValidationError):
        TenderInspectionResult(
            tender_id="x",
            state=ProcedureState.ACTIVE,
            verified=True,
            attempted_at=NOW,
            error_category=InspectionErrorCategory.NETWORK,
        )
    with pytest.raises(ValidationError):
        TenderInspectionResult(
            tender_id="x",
            attempted_at=NOW,
            raw_data_updates={"password": "secret"},
        )


def test_contract_round_trip_preserves_verified_result() -> None:
    result = TenderInspectionResult(
        tender_id="x",
        state=ProcedureState.ACTIVE,
        verified=True,
        attempted_at=NOW,
        raw_data_updates={"inspection_mode": "endpoint"},
    )

    restored = TenderInspectionResult.model_validate(result.model_dump())

    assert restored == result
    assert "secret" not in repr(restored)
