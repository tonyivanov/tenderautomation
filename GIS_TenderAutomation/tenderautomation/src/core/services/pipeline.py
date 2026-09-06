from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone

from core.events.bus import EventBus
from core.logging import get_logger
from core.services.collection import CollectionService, CollectionSummary
from core.services.qualification import QualificationResult, QualificationService

log = get_logger(__name__)


@dataclass
class PipelineResult:
    started_at: datetime
    completed_at: datetime
    collection: CollectionSummary
    qualification: QualificationResult

    @property
    def duration_sec(self) -> float:
        return (self.completed_at - self.started_at).total_seconds()


class PipelineOrchestrator:
    def __init__(
        self,
        collection_service: CollectionService,
        qualification_service: QualificationService,
        event_bus: EventBus,
    ) -> None:
        self._collection = collection_service
        self._qualification = qualification_service
        self._event_bus = event_bus

    def run(self) -> PipelineResult:
        """Run from a synchronous process entry point."""
        return asyncio.run(self.run_async())

    async def run_async(self) -> PipelineResult:
        """Run without nesting an event loop."""
        started_at = datetime.now(timezone.utc)
        log.info("pipeline_start", extra={"context": {"started_at": started_at.isoformat()}})

        collection_summary = await self._collection.run_all()

        qualification_result = self._qualification.qualify_pending()

        if qualification_result.qualified_count > 0:
            self._event_bus.publish(
                "tenders_qualified",
                count=qualification_result.qualified_count,
                platform_summary=collection_summary.by_platform(),
            )

        completed_at = datetime.now(timezone.utc)
        result = PipelineResult(
            started_at=started_at,
            completed_at=completed_at,
            collection=collection_summary,
            qualification=qualification_result,
        )
        log.info(
            "pipeline_complete",
            extra={"context": {
                "duration_sec": result.duration_sec,
                "new_tenders": collection_summary.total_new,
                "qualified": qualification_result.qualified_count,
            }},
        )
        return result
