from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any, TypeVar

from core.adapters import AdapterRegistry
from core.logging import get_logger
from core.models import (
    AuthSession,
    ExportOutcome,
    ExportOutcomeCategory,
    ExportPreparationResult,
    ExportPreparationSummary,
    ExportRequest,
    InspectionApplyStatus,
    PreparedTender,
    TenderModel,
    V3LookupResult,
    V3LookupState,
)
from core.repositories import TenderRepository
from core.services.export_decisions import (
    completeness_warnings,
    inspection_required,
    is_archive_candidate,
    is_classification_eligible,
    merge_verified_fields,
)
from core.services.v3_export import V3ExportProjection

log = get_logger(__name__)
T = TypeVar("T")


class BlockingIOBridge:
    def __init__(self, limit: int = 4) -> None:
        self._semaphore = asyncio.Semaphore(limit)

    async def run(self, function: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        async with self._semaphore:
            return await asyncio.to_thread(function, *args, **kwargs)


class ExportReadinessService:
    def __init__(
        self,
        registry: AdapterRegistry,
        repository: TenderRepository,
        projection: V3ExportProjection,
        credentials_for: Callable[[str], Any],
        *,
        clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
        external_concurrency: int = 4,
        operation_timeout: float = 30.0,
        batch_timeout: float = 120.0,
    ) -> None:
        self._registry = registry
        self._repository = repository
        self._projection = projection
        self._credentials_for = credentials_for
        self._clock = clock
        self._external_concurrency = external_concurrency
        self._operation_timeout = min(operation_timeout, 30.0)
        self._batch_timeout = min(batch_timeout, 120.0)

    async def prepare(self, request: ExportRequest) -> ExportPreparationResult:
        started = time.monotonic()
        bridge = BlockingIOBridge()
        if request.tender_ids is None:
            refs = await bridge.run(self._projection.list_eligible_refs, limit=request.limit)
            additional_ids = tuple(ref.tender_id for ref in refs if ref.tender_id)
            additional_titles = tuple(ref.title for ref in refs if ref.title)
        else:
            additional_ids = additional_titles = ()
        candidates = await bridge.run(
            self._repository.get_export_candidates,
            request.tender_ids,
            limit=request.limit,
            additional_ids=additional_ids,
            additional_titles=additional_titles,
        )
        lookups = await bridge.run(self._projection.get_many, tuple(candidates))
        external = asyncio.Semaphore(self._external_concurrency)
        sessions: dict[str, AuthSession] = {}
        session_locks: dict[str, asyncio.Lock] = {}

        async def session_for(tender: TenderModel) -> AuthSession:
            lock = session_locks.setdefault(tender.platform, asyncio.Lock())
            async with lock:
                existing = sessions.get(tender.platform)
                if existing is not None:
                    return existing
                adapter = self._registry.get(tender.platform)
                credentials = self._credentials_for(tender.platform)
                async with external:
                    session = await asyncio.wait_for(
                        adapter.authenticate(credentials), timeout=self._operation_timeout
                    )
                sessions[tender.platform] = session
                return session

        async def prepare_one(tender: TenderModel) -> ExportOutcome:
            lookup = lookups.get(
                tender.id, V3LookupResult(state=V3LookupState.NOT_FOUND)
            )
            if (
                lookup.state is V3LookupState.UNAVAILABLE
                and tender.qualification_tier != "qualified"
            ):
                return self._outcome(tender.id, ExportOutcomeCategory.UNVERIFIED, "v3_unavailable")
            if not is_classification_eligible(tender, lookup):
                return self._outcome(tender.id, ExportOutcomeCategory.INELIGIBLE, "classification")
            now = self._clock()
            if not inspection_required(tender, now):
                return self._classified_outcome(tender, lookup, now, "cached")
            try:
                adapter = self._registry.get(tender.platform)
                session = await session_for(tender)
                async with external:
                    inspection = await asyncio.wait_for(
                        adapter.inspect_tender(session, tender, descriptor=None),
                        timeout=self._operation_timeout,
                    )
                if inspection.tender_id != tender.id:
                    return self._outcome(tender.id, ExportOutcomeCategory.UNVERIFIED, "contract")
                apply_result = await bridge.run(self._repository.apply_inspection, inspection)
                if apply_result.status in {
                    InspectionApplyStatus.CONFLICT,
                    InspectionApplyStatus.STALE,
                    InspectionApplyStatus.MISSING,
                }:
                    return self._outcome(
                        tender.id, ExportOutcomeCategory.UNVERIFIED, apply_result.status.value
                    )
                if not inspection.verified:
                    return self._outcome(tender.id, ExportOutcomeCategory.UNVERIFIED, "inspection")
                refreshed = merge_verified_fields(tender, inspection)
                return self._classified_outcome(refreshed, lookup, now, "verified")
            except asyncio.CancelledError:
                raise
            except (TimeoutError, OSError, ConnectionError, PermissionError, ValueError):
                return self._outcome(tender.id, ExportOutcomeCategory.UNVERIFIED, "external")
            except Exception:
                return self._outcome(tender.id, ExportOutcomeCategory.UNVERIFIED, "internal")

        tasks = {tender.id: asyncio.create_task(prepare_one(tender)) for tender in candidates}
        if tasks:
            done, pending = await asyncio.wait(tasks.values(), timeout=self._batch_timeout)
        else:
            done, pending = set(), set()
        for task in pending:
            task.cancel()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)
        completed = {task: task.result() for task in done if not task.cancelled()}
        by_id = {outcome.tender_id: outcome for outcome in completed.values()}

        ordered_ids = (
            list(request.tender_ids)
            if request.tender_ids is not None
            else [tender.id for tender in candidates]
        )
        outcomes: list[ExportOutcome] = []
        candidate_ids = {tender.id for tender in candidates}
        for tender_id in ordered_ids:
            if tender_id not in candidate_ids:
                outcomes.append(self._outcome(tender_id, ExportOutcomeCategory.MISSING, "missing"))
            else:
                outcomes.append(
                    by_id.get(
                        tender_id,
                        self._outcome(tender_id, ExportOutcomeCategory.UNVERIFIED, "batch_timeout"),
                    )
                )
        summary = self._summary(outcomes)
        log.info(
            "export_readiness_complete",
            extra={
                "context": {
                    **summary.model_dump(),
                    "duration_ms": round((time.monotonic() - started) * 1000),
                }
            },
        )
        return ExportPreparationResult(outcomes=tuple(outcomes), summary=summary)

    @staticmethod
    def _outcome(
        tender_id: str, category: ExportOutcomeCategory, reason: str
    ) -> ExportOutcome:
        return ExportOutcome(tender_id=tender_id, category=category, reason=reason)

    @staticmethod
    def _classified_outcome(
        tender: TenderModel, lookup: V3LookupResult, now: datetime, reason: str
    ) -> ExportOutcome:
        if is_archive_candidate(tender, now):
            return ExportOutcome(
                tender_id=tender.id,
                category=ExportOutcomeCategory.ARCHIVE,
                reason=reason,
            )
        if tender.procedure_state.value != "active":
            return ExportOutcome(
                tender_id=tender.id,
                category=ExportOutcomeCategory.UNVERIFIED,
                reason="unknown_state",
            )
        return ExportOutcome(
            tender_id=tender.id,
            category=ExportOutcomeCategory.READY,
            prepared=PreparedTender(
                tender=tender,
                v3=lookup.context,
                completeness_warnings=completeness_warnings(tender),
            ),
            reason=reason,
        )

    @staticmethod
    def _summary(outcomes: list[ExportOutcome]) -> ExportPreparationSummary:
        counts = {category: 0 for category in ExportOutcomeCategory}
        for outcome in outcomes:
            counts[outcome.category] += 1
        return ExportPreparationSummary(
            requested=len(outcomes),
            ready=counts[ExportOutcomeCategory.READY],
            archive=counts[ExportOutcomeCategory.ARCHIVE],
            ineligible=counts[ExportOutcomeCategory.INELIGIBLE],
            unverified=counts[ExportOutcomeCategory.UNVERIFIED],
            missing=counts[ExportOutcomeCategory.MISSING],
        )
