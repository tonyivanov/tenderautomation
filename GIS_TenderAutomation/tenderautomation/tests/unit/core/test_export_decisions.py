from datetime import datetime, timedelta, timezone

from core.models import (
    ProcedureState,
    TenderInspectionResult,
    V3ExportContext,
    V3LookupResult,
    V3LookupState,
)
from core.services.export_decisions import (
    completeness_warnings,
    inspection_required,
    is_archive_candidate,
    is_classification_eligible,
    is_inspection_fresh,
    merge_verified_fields,
)


NOW = datetime(2026, 7, 23, tzinfo=timezone.utc)


def test_v3_p2_overrides_legacy_filtered(tender_factory) -> None:
    tender = tender_factory(qualification_tier="filtered")
    lookup = V3LookupResult(
        state=V3LookupState.FOUND,
        context=V3ExportContext(queue="P2"),
    )
    assert is_classification_eligible(tender, lookup)


def test_ttl_boundary_is_exact(tender_factory) -> None:
    fresh = tender_factory(
        procedure_checked_at=NOW - timedelta(hours=24) + timedelta(microseconds=1)
    )
    stale = tender_factory(procedure_checked_at=NOW - timedelta(hours=24))
    assert is_inspection_fresh(fresh, NOW)
    assert not is_inspection_fresh(stale, NOW)


def test_unknown_needs_inspection_and_inactive_archives(tender_factory) -> None:
    unknown = tender_factory(procedure_state=ProcedureState.UNKNOWN)
    closed = tender_factory(procedure_state=ProcedureState.CLOSED)
    assert inspection_required(unknown, NOW)
    assert is_archive_candidate(closed, NOW)


def test_verified_merge_never_erases_non_null_values(tender_factory) -> None:
    tender = tender_factory(buyer="Known", description="Known description")
    result = TenderInspectionResult(
        tender_id=tender.id,
        state=ProcedureState.ACTIVE,
        verified=True,
        attempted_at=NOW,
        buyer=None,
        description=None,
    )
    merged = merge_verified_fields(tender, result)
    assert merged.buyer == "Known"
    assert merged.description == "Known description"
    assert merged.procedure_state is ProcedureState.ACTIVE
    assert merged.status == tender.status


def test_budget_absence_is_not_a_completeness_warning(tender_factory) -> None:
    warnings = completeness_warnings(tender_factory(budget=None))
    assert "missing_budget" not in warnings
