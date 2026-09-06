import asyncio
from datetime import datetime, timezone

from core.adapters import AdapterRegistry, PlatformAdapter
from core.models import (
    AuthSession,
    ExportOutcomeCategory,
    ExportRequest,
    InspectionApplyResult,
    InspectionApplyStatus,
    PlatformCredentials,
    ProcedureState,
    TenderInspectionResult,
    V3ExportContext,
    V3LookupResult,
    V3LookupState,
)
from core.services.export_readiness import ExportReadinessService


NOW = datetime(2026, 7, 23, tzinfo=timezone.utc)


class FakeAdapter(PlatformAdapter):
    calls = 0

    def platform_id(self): return "bidzaar"
    async def authenticate(self, credentials): return AuthSession(platform="bidzaar", token="opaque")
    async def fetch_new(self, session, since, descriptor): return []
    def map_to_tender(self, raw, descriptor): raise NotImplementedError
    async def inspect_tender(self, session, tender, descriptor):
        self.calls += 1
        return TenderInspectionResult(
            tender_id=tender.id, state=ProcedureState.ACTIVE,
            verified=True, attempted_at=NOW,
        )


class FakeRepository:
    def __init__(self, tenders): self.tenders = tenders
    def get_export_candidates(self, tender_ids, **kwargs):
        if tender_ids is None: return self.tenders
        by_id = {t.id: t for t in self.tenders}
        return [by_id[i] for i in tender_ids if i in by_id]
    def apply_inspection(self, inspection):
        return InspectionApplyResult(tender_id=inspection.tender_id, status=InspectionApplyStatus.APPLIED)


class FakeProjection:
    def __init__(self, state=V3LookupState.FOUND): self.state = state
    def list_eligible_refs(self, limit=50): return ()
    def get_many(self, tenders):
        return {
            t.id: V3LookupResult(
                state=self.state,
                context=(V3ExportContext(queue="P2") if self.state is V3LookupState.FOUND else None),
            ) for t in tenders
        }


def _service(tenders, projection=None):
    registry = AdapterRegistry(); registry.register(FakeAdapter())
    return ExportReadinessService(
        registry, FakeRepository(tenders), projection or FakeProjection(),
        lambda platform: PlatformCredentials(platform=platform, username="u", password="p"),
        clock=lambda: NOW,
    )


def test_prepare_verifies_filtered_v3_p2_and_returns_ready(tender_factory) -> None:
    tender = tender_factory(qualification_tier="filtered")
    result = asyncio.run(_service([tender]).prepare(ExportRequest(tender_ids=(tender.id,), requested_at=NOW)))
    assert result.outcomes[0].category is ExportOutcomeCategory.READY
    assert result.summary.ready == 1


def test_missing_explicit_id_is_partitioned(tender_factory) -> None:
    result = asyncio.run(_service([]).prepare(ExportRequest(tender_ids=("missing",), requested_at=NOW)))
    assert result.outcomes[0].category is ExportOutcomeCategory.MISSING


def test_v3_unavailable_filtered_fails_closed_without_platform_call(tender_factory) -> None:
    adapter = FakeAdapter(); adapter.calls = 0
    registry = AdapterRegistry(); registry.register(adapter)
    tender = tender_factory(qualification_tier="filtered")
    service = ExportReadinessService(
        registry, FakeRepository([tender]), FakeProjection(V3LookupState.UNAVAILABLE),
        lambda p: PlatformCredentials(platform=p, username="u", password="p"),
        clock=lambda: NOW,
    )
    result = asyncio.run(service.prepare(ExportRequest(tender_ids=(tender.id,), requested_at=NOW)))
    assert result.outcomes[0].category is ExportOutcomeCategory.UNVERIFIED
    assert adapter.calls == 0
