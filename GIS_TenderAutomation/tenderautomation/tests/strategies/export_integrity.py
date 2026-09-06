from datetime import datetime, timezone

from hypothesis import strategies as st

from core.models import ProcedureState, TenderInspectionResult, TenderModel


aware_datetimes = st.datetimes(
    min_value=datetime(2020, 1, 1),
    max_value=datetime(2035, 1, 1),
    timezones=st.just(timezone.utc),
)
procedure_states = st.sampled_from(list(ProcedureState))
provenance = st.fixed_dictionaries(
    {}, optional={
        "inspection_mode": st.sampled_from(["endpoint", "playwright"]),
        "http_status": st.integers(min_value=100, max_value=599),
        "detail_available": st.booleans(),
    }
)
state_sequences = st.lists(procedure_states, min_size=0, max_size=20)


@st.composite
def tenders(draw, *, state: ProcedureState | None = None):
    procedure_state = state or draw(procedure_states)
    identifier = draw(st.integers(min_value=1, max_value=1_000_000))
    return TenderModel(
        id=f"bidzaar_{identifier}",
        platform="bidzaar",
        external_id=str(identifier),
        title=draw(st.text(min_size=1, max_size=60)),
        buyer=draw(st.one_of(st.none(), st.text(min_size=1, max_size=60))),
        deadline=draw(st.one_of(st.none(), aware_datetimes)),
        description=draw(st.one_of(st.none(), st.text(min_size=1, max_size=100))),
        url=f"https://example.test/{identifier}",
        qualification_tier=draw(st.sampled_from([None, "qualified", "filtered"])),
        procedure_state=procedure_state,
        procedure_checked_at=draw(st.one_of(st.none(), aware_datetimes)),
    )


@st.composite
def inspections(draw, *, tender_id: str = "bidzaar_1"):
    verified = draw(st.booleans())
    return TenderInspectionResult(
        tender_id=tender_id,
        state=(draw(st.sampled_from(list(ProcedureState))) if verified else ProcedureState.UNKNOWN),
        verified=verified,
        attempted_at=draw(aware_datetimes),
        buyer=draw(st.one_of(st.none(), st.text(min_size=1, max_size=60))),
    )
