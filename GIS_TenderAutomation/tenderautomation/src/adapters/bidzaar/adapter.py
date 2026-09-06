from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import yaml

from core.adapters.base import PlatformAdapter
from core.models import AuthSession, PlatformCredentials, PlatformDescriptor, RawTender, TenderModel
from core.models.tender import TenderStatus
from .auth import BidzaarAuth
from .api_client import BidzaarApiClient

_DESCRIPTOR_PATH = Path(__file__).parent / "descriptor.yaml"


def _load_descriptor() -> PlatformDescriptor:
    with open(_DESCRIPTOR_PATH, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return PlatformDescriptor(**data)


class BidzaarAdapter(PlatformAdapter):
    def __init__(self) -> None:
        self._descriptor = _load_descriptor()

    def platform_id(self) -> str:
        return "bidzaar"

    async def authenticate(self, credentials: PlatformCredentials) -> AuthSession:
        auth = BidzaarAuth(self._descriptor)
        return await auth.async_get_session(credentials)

    async def fetch_new(
        self,
        session: AuthSession,
        since: datetime | None,
        descriptor: PlatformDescriptor,
    ) -> list[RawTender]:
        client = BidzaarApiClient(session, self._descriptor)
        return await client.fetch_new(since)

    def map_to_tender(self, raw: RawTender, descriptor: PlatformDescriptor) -> TenderModel:
        item = raw.raw
        tender_id = f"bidzaar_{raw.external_id}"

        title = (item.get("name") or "").strip()
        if not title:
            raise ValueError(f"Bidzaar tender {raw.external_id} has empty name")
        url = f"https://bidzaar.com/app/process/light/{raw.external_id}"

        budget: Decimal | None = None
        if item.get("startPrice") is not None:
            try:
                budget = Decimal(str(item["startPrice"]))
            except Exception:
                budget = None

        deadline: datetime | None = None
        if item.get("finishDate"):
            try:
                deadline = datetime.fromisoformat(
                    item["finishDate"].replace("Z", "+00:00")
                )
            except ValueError:
                pass
        # Fallback: use _deadline from detail API (parameters.acceptanceEndDate)
        if deadline is None:
            from .api_client import BidzaarApiClient
            deadline = BidzaarApiClient._extract_deadline_from_raw(item)

        published_at: datetime | None = None
        if item.get("startDate"):
            try:
                published_at = datetime.fromisoformat(
                    item["startDate"].replace("Z", "+00:00")
                )
            except ValueError:
                pass

        return TenderModel(
            id=tender_id,
            platform="bidzaar",
            external_id=raw.external_id,
            title=title,
            buyer=item.get("organizationName") or None,
            budget=budget,
            deadline=deadline,
            description=item.get("description") or None,
            url=url,
            raw_data=item,
            published_at=published_at,
            status=TenderStatus.PENDING,
        )
