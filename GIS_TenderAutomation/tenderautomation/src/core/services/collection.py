from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field

from core.adapters import AdapterRegistry, PlatformAdapter
from core.config import settings
from core.logging import get_logger
from core.models import CollectionResult, PlatformCredentials
from core.repositories import TenderRepository

log = get_logger(__name__)

_RETRYABLE_EXCEPTIONS = (OSError, TimeoutError, ConnectionError)


def credentials_for(platform_id: str) -> PlatformCredentials:
    if platform_id == "b2bcenter":
        return PlatformCredentials(
            platform=platform_id,
            username=settings.b2bcenter_username,
            password=settings.b2bcenter_password,
        )
    if platform_id == "bidzaar":
        return PlatformCredentials(
            platform=platform_id,
            username=settings.bidzaar_username,
            password=settings.bidzaar_password,
        )
    raise ValueError(f"Unknown platform: {platform_id}")


@dataclass
class CollectionSummary:
    results: list[CollectionResult] = field(default_factory=list)

    def by_platform(self) -> dict[str, int]:
        return {r.platform: r.new_count for r in self.results}

    @property
    def total_new(self) -> int:
        return sum(r.new_count for r in self.results)


class CollectionService:
    def __init__(self, registry: AdapterRegistry, tender_repo: TenderRepository) -> None:
        self._registry = registry
        self._tender_repo = tender_repo

    async def run_for_platform(self, adapter: PlatformAdapter) -> CollectionResult:
        platform_id = adapter.platform_id()
        credentials = credentials_for(platform_id)
        since = self._tender_repo.get_last_success_at(platform_id)

        # Note: Bidzaar sorts by UUID desc (newest first), so MAX_PAGES=50 always
        # gives the most recent ~1250 tenders regardless of last_success_at
        if since is None:
            log.info("collection_first_run",
                     extra={"context": {"platform": platform_id, "max_pages": "using adapter default"}})

        max_retries = settings.collection_max_retries
        base_delay = settings.collection_retry_base_sec

        for attempt in range(1, max_retries + 1):
            try:
                session = await adapter.authenticate(credentials)
                # Descriptor loaded by adapter itself from its YAML file
                raw_tenders = await adapter.fetch_new(session, since, descriptor=None)
                tenders = [adapter.map_to_tender(raw, descriptor=None) for raw in raw_tenders]
                result = self._tender_repo.save_batch(tenders)
                self._tender_repo.log_collection_run(
                    platform_id, "success",
                    new_count=result.new_count,
                    updated_count=result.updated_count,
                    attempt=attempt,
                )
                log.info(
                    "collection_success",
                    extra={"context": {"platform": platform_id, "new": result.new_count}},
                )
                return result

            except PermissionError as e:
                # Auth errors are not retryable
                self._tender_repo.log_collection_run(
                    platform_id, "auth_error", error=str(e), attempt=attempt
                )
                log.error(
                    "collection_auth_error",
                    extra={"context": {"platform": platform_id}},
                )
                return CollectionResult(platform=platform_id, success=False, error=str(e))

            except _RETRYABLE_EXCEPTIONS as e:
                if attempt == max_retries:
                    self._tender_repo.log_collection_run(
                        platform_id, "failed", error=str(e), attempt=attempt
                    )
                    log.warning(
                        "collection_failed",
                        extra={"context": {"platform": platform_id, "attempts": attempt}},
                    )
                    return CollectionResult(platform=platform_id, success=False, error=str(e))
                delay = base_delay * (2 ** (attempt - 1))
                log.warning(
                    "collection_retry",
                    extra={"context": {"platform": platform_id, "attempt": attempt, "delay": delay}},
                )
                await asyncio.sleep(delay)

        return CollectionResult(platform=platform_id, success=False)  # unreachable

    async def run_all(self) -> CollectionSummary:
        summary = CollectionSummary()
        for adapter in self._registry.get_all():
            result = await self.run_for_platform(adapter)
            summary.results.append(result)
        return summary
