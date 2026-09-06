from datetime import timedelta

from hypothesis import given, strategies as st

from core.models import (
    ExportOutcome,
    ExportOutcomeCategory,
    ProcedureState,
    TenderInspectionResult,
    TenderStatus,
    V3ExportContext,
    V3LookupResult,
    V3LookupState,
)
from core.services.export_decisions import (
    inspection_required,
    is_archive_candidate,
    is_classification_eligible,
    is_inspection_fresh,
    merge_verified_fields,
    validate_partition,
)
from tests.strategies.export_integrity import aware_datetimes, inspections, tenders


@given(tenders(), aware_datetimes)
def test_archive_decision_is_workflow_status_invariant(tender, now) -> None:
    expected = is_archive_candidate(tender, now)
    for status in TenderStatus:
        assert is_archive_candidate(tender.model_copy(update={"status": status}), now) == expected


@given(tenders(state=ProcedureState.UNKNOWN), aware_datetimes)
def test_unknown_always_requires_inspection(tender, now) -> None:
    assert inspection_required(tender, now)


@given(tenders(), aware_datetimes)
def test_ttl_boundary_property(tender, now) -> None:
    fresh = tender.model_copy(
        update={"procedure_checked_at": now - timedelta(hours=24) + timedelta(microseconds=1)}
    )
    stale = tender.model_copy(update={"procedure_checked_at": now - timedelta(hours=24)})
    assert is_inspection_fresh(fresh, now)
    assert not is_inspection_fresh(stale, now)


@given(tenders(), inspections())
def test_merge_is_null_preserving_and_idempotent(tender, inspection) -> None:
    inspection = inspection.model_copy(update={"tender_id": tender.id})
    once = merge_verified_fields(tender, inspection)
    twice = merge_verified_fields(once, inspection)
    for field in ("buyer", "budget", "deadline", "description", "published_at"):
        if getattr(inspection, field) is None:
            assert getattr(once, field) == getattr(tender, field)
    assert twice == once


@given(tenders(), inspections())
def test_unverified_failure_never_changes_tender(tender, inspection) -> None:
    failure = inspection.model_copy(
        update={"tender_id": tender.id, "verified": False, "state": ProcedureState.UNKNOWN}
    )
    assert merge_verified_fields(tender, failure) == tender


@given(tenders(), st.sampled_from([None, "P1", "P2", "Reject"]))
def test_eligibility_matches_simple_oracle(tender, queue) -> None:
    lookup = (
        V3LookupResult(
            state=V3LookupState.FOUND,
            context=V3ExportContext(queue=queue),
        )
        if queue is not None
        else V3LookupResult(state=V3LookupState.NOT_FOUND)
    )
    expected = queue in {"P1", "P2"} if queue is not None else tender.qualification_tier == "qualified"
    assert is_classification_eligible(tender, lookup) is expected


@given(st.lists(st.text(min_size=1, max_size=20), unique=True, max_size=50))
def test_partition_conserves_requested_ids(ids) -> None:
    outcomes = [
        ExportOutcome(
            tender_id=tender_id,
            category=ExportOutcomeCategory.UNVERIFIED,
            reason="generated",
        )
        for tender_id in reversed(ids)
    ]
    assert validate_partition(ids, outcomes)


@given(tenders(), aware_datetimes)
def test_latest_active_inspection_reopens_inactive_tender(tender, attempted_at) -> None:
    closed = tender.model_copy(update={"procedure_state": ProcedureState.CLOSED})
    reopened = merge_verified_fields(
        closed,
        TenderInspectionResult(
            tender_id=closed.id,
            state=ProcedureState.ACTIVE,
            verified=True,
            attempted_at=attempted_at,
        ),
    )
    assert reopened.procedure_state is ProcedureState.ACTIVE
