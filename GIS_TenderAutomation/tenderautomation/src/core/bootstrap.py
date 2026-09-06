from __future__ import annotations

from core.adapters import AdapterRegistry
from core.config import settings
from core.events import EventBus
from core.repositories import QualifiedLogRepository, TenderRepository
from core.services.collection import CollectionService
from core.services.collection import credentials_for
from core.services.export_readiness import ExportReadinessService
from core.services.pipeline import PipelineOrchestrator
from core.services.qualification import QualificationService
from core.services.qualification_engine import QualificationEngine
from core.services.reconciliation import ReconciliationService
from core.services.v3_export import V3ExportProjection


def build_adapter_registry() -> AdapterRegistry:
    from adapters.b2bcenter import B2BCenterAdapter
    from adapters.bidzaar import BidzaarAdapter

    registry = AdapterRegistry()
    registry.register(B2BCenterAdapter())
    registry.register(BidzaarAdapter())
    return registry


def build_pipeline(
    event_bus: EventBus, *, register_notifications: bool = False
) -> PipelineOrchestrator:
    if register_notifications:
        from notifications.handler import NotificationHandler
        from notifications.telegram import TelegramNotifier

        notifier = TelegramNotifier(
            bot_token=settings.telegram_bot_token,
            chat_ids=settings.get_telegram_chat_ids(),
            web_base_url=settings.web_base_url,
        )
        NotificationHandler(notifier).register(event_bus)

    tender_repo = TenderRepository()
    collection_svc = CollectionService(build_adapter_registry(), tender_repo)
    qualification_svc = QualificationService(
        QualificationEngine.from_filters_dir(settings.filters_dir),
        tender_repo,
        QualifiedLogRepository(settings.data_dir),
    )
    return PipelineOrchestrator(collection_svc, qualification_svc, event_bus)


def build_reconciliation_service() -> ReconciliationService:
    return ReconciliationService(build_adapter_registry(), TenderRepository())


def build_export_readiness_service() -> ExportReadinessService:
    """Compose export readiness without opening databases or platform sessions."""
    return ExportReadinessService(
        build_adapter_registry(),
        TenderRepository(),
        V3ExportProjection(),
        credentials_for,
    )
