from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone

from core.models import (
    AuthSession,
    DeadlineExtractionOutcome,
    DeadlineExtractionState,
    PlatformCredentials,
    PlatformDescriptor,
    RawTender,
    TenderInspectionResult,
    TenderModel,
)


class PlatformAdapter(ABC):
    @abstractmethod
    def platform_id(self) -> str:
        """Unique platform slug, e.g. 'bidzaar', 'b2bcenter'."""

    @abstractmethod
    async def authenticate(self, credentials: PlatformCredentials) -> AuthSession:
        """Authenticate and return a session. Raises AuthError on failure."""

    @abstractmethod
    async def fetch_new(
        self,
        session: AuthSession,
        since: datetime | None,
        descriptor: PlatformDescriptor | None,
    ) -> list[RawTender]:
        """Fetch tenders published after `since`. Respects descriptor rate limits."""

    @abstractmethod
    def map_to_tender(
        self, raw: RawTender, descriptor: PlatformDescriptor | None
    ) -> TenderModel:
        """Map platform-specific raw data to unified TenderModel."""

    def canonical_url(self, tender: TenderModel) -> str:
        """Return the internally trusted detail URL for an existing tender."""
        return tender.url

    async def enrich_deadline(
        self,
        session: AuthSession,
        tender: TenderModel,
        descriptor: PlatformDescriptor | None,
    ) -> DeadlineExtractionOutcome:
        """Resolve a missing deadline; adapters may keep the safe missing default."""
        return DeadlineExtractionOutcome(
            deadline=None,
            state=DeadlineExtractionState.MISSING,
        )

    async def inspect_tender(
        self,
        session: AuthSession,
        tender: TenderModel,
        descriptor: PlatformDescriptor | None,
    ) -> TenderInspectionResult:
        """Inspect current procedure state; concrete adapters opt in during EI-2."""
        return TenderInspectionResult(
            tender_id=tender.id,
            attempted_at=datetime.now(timezone.utc),
        )
