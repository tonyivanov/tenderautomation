import asyncio
from contextlib import contextmanager
from datetime import datetime, timezone
from unittest.mock import AsyncMock

from hypothesis import given
from hypothesis import strategies as st

from core.adapters import AdapterRegistry
from core.models import (
    AuthSession,
    DeadlineExtractionOutcome,
    DeadlineExtractionState,
    DeadlineSource,
    NormalizedDeadline,
    ReconciliationCommand,
    TenderModel,
)
from core.services.reconciliation import ReconciliationService


class FakeRepository:
    def __init__(self, candidates, *, acquired: bool = True) -> None:
        self.candidates = list(candidates)
        self.acquired = acquired
        self.updates = []

    @contextmanager
    def reconciliation_lock(self):
        yield self.acquired

    def get_reconciliation_candidates(self, limit: int):
        return self.candidates[:limit]

    def count_reconciliation_candidates(self) -> int:
        return len(self.candidates)

    def apply_reconciliation_update(self, tender_id: str, **changes):
        self.updates.append((tender_id, changes))
        deadline_updated = changes.get("deadline") is not None
        url_updated = changes.get("url") is not None and not changes["url"].endswith("legacy")
        return deadline_updated, url_updated


class StatefulRepository(FakeRepository):
    def get_reconciliation_candidates(self, limit: int):
        return [
            tender
            for tender in self.candidates
            if tender.deadline is None or tender.url == "legacy"
        ][:limit]

    def count_reconciliation_candidates(self) -> int:
        return len(self.get_reconciliation_candidates(200))

    def apply_reconciliation_update(self, tender_id: str, **changes):
        tender = next(t for t in self.candidates if t.id == tender_id)
        deadline_updated = tender.deadline is None and changes.get("deadline") is not None
        url_updated = changes.get("url") is not None and tender.url != changes["url"]
        if deadline_updated:
            tender.deadline = changes["deadline"]
        if url_updated:
            tender.url = changes["url"]
        self.updates.append((tender_id, changes))
        return deadline_updated, url_updated


class FakeAdapter:
    def __init__(self, platform: str, outcome: DeadlineExtractionOutcome) -> None:
        self._platform = platform
        self.outcome = outcome
        self.authenticate = AsyncMock(return_value=AuthSession(platform=platform))
        self.enrich_deadline = AsyncMock(return_value=outcome)

    def platform_id(self) -> str:
        return self._platform

    def canonical_url(self, tender) -> str:
        return f"https://bidzaar.com/app/process/light/{tender.external_id}"


def _service(tenders, outcome, *, acquired: bool = True):
    adapter = FakeAdapter("bidzaar", outcome)
    registry = AdapterRegistry()
    registry.register(adapter)  # type: ignore[arg-type]
    repository = FakeRepository(tenders, acquired=acquired)
    return ReconciliationService(registry, repository), adapter, repository


def _tender(index: int) -> TenderModel:
    return TenderModel(
        id=f"bidzaar_{index}",
        platform="bidzaar",
        external_id=str(index),
        title="Tender",
        deadline=None,
        url=f"https://bidzaar.com/app/process/light/{index}",
    )


def test_partial_run_updates_url_and_deadline_once(tender_factory) -> None:
    tender = tender_factory(deadline=None, url="legacy")
    outcome = DeadlineExtractionOutcome(
        NormalizedDeadline(
            datetime(2026, 8, 1, tzinfo=timezone.utc), DeadlineSource.DETAIL
        ),
        DeadlineExtractionState.RESOLVED,
    )
    service, adapter, repository = _service([tender], outcome)
    result = asyncio.run(
        service.run(ReconciliationCommand(batch_size=1))
    )
    assert result.scanned == 1
    assert result.url_updated == 1
    assert result.deadline_updated == 1
    assert result.failed == 0
    adapter.authenticate.assert_awaited_once()
    adapter.enrich_deadline.assert_awaited_once()
    assert len(repository.updates) == 2


def test_external_failure_is_counted_without_losing_url(tender_factory) -> None:
    tender = tender_factory(deadline=None, url="legacy")
    outcome = DeadlineExtractionOutcome(
        None, DeadlineExtractionState.INVALID
    )
    service, _, _ = _service([tender], outcome)
    result = asyncio.run(service.run(ReconciliationCommand()))
    assert result.url_updated == 1
    assert result.unresolved == 1


def test_existing_deadline_is_never_enriched(tender_factory) -> None:
    tender = tender_factory(url="legacy")
    outcome = DeadlineExtractionOutcome(None, DeadlineExtractionState.MISSING)
    service, adapter, _ = _service([tender], outcome)
    result = asyncio.run(service.run(ReconciliationCommand()))
    assert result.scanned == 1
    assert result.url_updated == 1
    assert result.deadline_updated == 0
    adapter.authenticate.assert_not_awaited()
    adapter.enrich_deadline.assert_not_awaited()


def test_unavailable_lock_returns_already_running(tender_factory) -> None:
    service, adapter, _ = _service(
        [tender_factory(deadline=None)],
        DeadlineExtractionOutcome(None, DeadlineExtractionState.MISSING),
        acquired=False,
    )
    result = asyncio.run(service.run(ReconciliationCommand()))
    assert result.already_running is True
    assert result.scanned == 0
    adapter.authenticate.assert_not_awaited()


def test_rerun_is_idempotent_and_authenticates_platform_once(tender_factory) -> None:
    tenders = [
        tender_factory(id=f"bidzaar_{index}", external_id=str(index), deadline=None, url="legacy")
        for index in range(2)
    ]
    outcome = DeadlineExtractionOutcome(
        NormalizedDeadline(
            datetime(2026, 8, 1, tzinfo=timezone.utc), DeadlineSource.DETAIL
        ),
        DeadlineExtractionState.RESOLVED,
    )
    adapter = FakeAdapter("bidzaar", outcome)
    registry = AdapterRegistry()
    registry.register(adapter)  # type: ignore[arg-type]
    repository = StatefulRepository(tenders)
    service = ReconciliationService(registry, repository)

    first = asyncio.run(service.run(ReconciliationCommand()))
    second = asyncio.run(service.run(ReconciliationCommand()))

    assert (first.deadline_updated, first.url_updated) == (2, 2)
    assert first.remaining_candidates == 0
    assert second.scanned == 0
    assert second.deadline_updated == second.url_updated == 0
    adapter.authenticate.assert_awaited_once()


@given(st.integers(min_value=1, max_value=200))
def test_processed_count_never_exceeds_batch(batch_size: int) -> None:
    tenders = [_tender(i) for i in range(5)]
    service, _, _ = _service(
        tenders, DeadlineExtractionOutcome(None, DeadlineExtractionState.MISSING)
    )
    result = asyncio.run(
        service.run(ReconciliationCommand(batch_size=batch_size))
    )
    assert 0 <= result.scanned <= min(batch_size, len(tenders))
