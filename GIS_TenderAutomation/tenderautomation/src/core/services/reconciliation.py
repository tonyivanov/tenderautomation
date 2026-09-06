from __future__ import annotations

from core.adapters import AdapterRegistry, PlatformAdapter
from core.logging import get_logger
from core.models import (
    AuthSession,
    DeadlineExtractionState,
    ReconciliationCommand,
    ReconciliationResult,
    TenderModel,
)
from core.repositories import TenderRepository
from core.services.collection import credentials_for
from core.services.deadlines import provenance

log = get_logger(__name__)


class ReconciliationService:
    def __init__(
        self, registry: AdapterRegistry, tender_repo: TenderRepository
    ) -> None:
        self._registry = registry
        self._tender_repo = tender_repo

    async def run(self, command: ReconciliationCommand) -> ReconciliationResult:
        result = ReconciliationResult()
        with self._tender_repo.reconciliation_lock() as acquired:
            if not acquired:
                result.already_running = True
                result.remaining_candidates = (
                    self._tender_repo.count_reconciliation_candidates()
                )
                return result

            candidates = self._tender_repo.get_reconciliation_candidates(
                command.batch_size
            )
            sessions: dict[str, AuthSession] = {}
            for tender in candidates:
                result.scanned += 1
                try:
                    adapter = self._registry.get(tender.platform)
                    if self._normalize_url(adapter, tender):
                        result.url_updated += 1

                    if tender.deadline is not None:
                        continue
                    session = sessions.get(tender.platform)
                    if session is None:
                        session = await adapter.authenticate(
                            credentials_for(tender.platform)
                        )
                        sessions[tender.platform] = session
                    outcome = await adapter.enrich_deadline(
                        session, tender, descriptor=None
                    )
                    if outcome.deadline is not None:
                        deadline_updated, _ = (
                            self._tender_repo.apply_reconciliation_update(
                                tender.id,
                                deadline=outcome.deadline.value,
                                raw_data_updates=provenance(outcome),
                            )
                        )
                        result.deadline_updated += int(deadline_updated)
                    elif outcome.state is DeadlineExtractionState.EXTERNAL_FAILURE:
                        result.failed += 1
                    else:
                        result.unresolved += 1
                except Exception as exc:
                    result.failed += 1
                    log.warning(
                        "deadline_reconciliation_row_failed",
                        extra={
                            "context": {
                                "platform": tender.platform,
                                "tender_id": tender.id,
                                "error_type": type(exc).__name__,
                            }
                        },
                    )

            result.remaining_candidates = (
                self._tender_repo.count_reconciliation_candidates()
            )
            return result

    def _normalize_url(
        self, adapter: PlatformAdapter, tender: TenderModel
    ) -> bool:
        canonical_url = adapter.canonical_url(tender)
        _, url_updated = self._tender_repo.apply_reconciliation_update(
            tender.id, url=canonical_url
        )
        return url_updated
