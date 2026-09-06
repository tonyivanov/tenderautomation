from datetime import datetime, timezone

from hypothesis import given, strategies as st

from core.models import ProcedureState, TenderInspectionResult
from core.services.export_decisions import merge_verified_fields
from tests.strategies.export_integrity import tenders


NOW = datetime(2026, 7, 23, tzinfo=timezone.utc)


@given(tenders(), st.lists(st.sampled_from(list(ProcedureState)), min_size=1, max_size=20))
def test_latest_verified_sequence_controls_procedure_state(tender, states) -> None:
    for index, state in enumerate(states):
        tender = merge_verified_fields(
            tender,
            TenderInspectionResult(
                tender_id=tender.id,
                state=state,
                verified=True,
                attempted_at=NOW.replace(microsecond=index),
            ),
        )
    assert tender.procedure_state is states[-1]
