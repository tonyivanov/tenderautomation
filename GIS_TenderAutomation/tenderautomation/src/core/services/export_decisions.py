from __future__ import annotations

from datetime import datetime, timedelta
from typing import Iterable

from core.models import (
    ExportOutcome,
    ProcedureState,
    TenderInspectionResult,
    TenderModel,
    V3LookupResult,
    V3LookupState,
)

INSPECTION_TTL = timedelta(hours=24)
INACTIVE_STATES = frozenset(
    {
        ProcedureState.CLOSED,
        ProcedureState.COMPLETED,
        ProcedureState.CANCELLED,
        ProcedureState.NOT_FOUND,
    }
)


def is_classification_eligible(
    tender: TenderModel, v3: V3LookupResult
) -> bool:
    if v3.state is V3LookupState.FOUND and v3.context is not None:
        return v3.context.queue in {"P1", "P2"}
    return tender.qualification_tier == "qualified"


def is_inspection_fresh(tender: TenderModel, now: datetime) -> bool:
    checked_at = tender.procedure_checked_at
    if checked_at is None:
        return False
    return now - checked_at < INSPECTION_TTL


def is_archive_candidate(tender: TenderModel, now: datetime) -> bool:
    if tender.procedure_state in INACTIVE_STATES:
        return True
    return tender.deadline is not None and tender.deadline < now


def inspection_required(tender: TenderModel, now: datetime) -> bool:
    if tender.procedure_state is ProcedureState.UNKNOWN:
        return True
    return not is_inspection_fresh(tender, now)


def merge_verified_fields(
    tender: TenderModel, inspection: TenderInspectionResult
) -> TenderModel:
    if not inspection.verified:
        return tender
    updates: dict[str, object] = {
        "procedure_state": inspection.state,
        "procedure_checked_at": inspection.attempted_at,
        "procedure_last_attempt_at": inspection.attempted_at,
        "procedure_source": inspection.source,
        "procedure_error_category": None,
    }
    for name in ("buyer", "budget", "deadline", "description", "published_at"):
        value = getattr(inspection, name)
        if value is not None:
            updates[name] = value
    if inspection.raw_data_updates:
        updates["raw_data"] = {**tender.raw_data, **inspection.raw_data_updates}
    return tender.model_copy(update=updates)


def completeness_warnings(tender: TenderModel) -> tuple[str, ...]:
    fields = ("buyer", "deadline", "description", "published_at")
    return tuple(f"missing_{name}" for name in fields if getattr(tender, name) is None)


def validate_partition(
    requested_ids: Iterable[str], outcomes: Iterable[ExportOutcome]
) -> bool:
    requested = list(requested_ids)
    outcome_ids = [outcome.tender_id for outcome in outcomes]
    return len(outcome_ids) == len(requested) and sorted(outcome_ids) == sorted(requested)
