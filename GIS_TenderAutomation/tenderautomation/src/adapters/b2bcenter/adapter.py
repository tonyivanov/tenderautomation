from __future__ import annotations

from datetime import datetime
from pathlib import Path

import httpx

from core.adapters.base import PlatformAdapter
from core.models import (
    AuthSession,
    DeadlineErrorCategory,
    DeadlineExtractionOutcome,
    DeadlineExtractionState,
    PlatformCredentials,
    PlatformDescriptor,
    RawTender,
    TenderModel,
)
from core.models.tender import TenderStatus, compute_content_hash
from .parsers import parse_deadline, parse_detail_deadline, parse_price
from .scraper import BROWSER_HEADERS, B2BCenterScraper

import yaml

_DESCRIPTOR_PATH = Path(__file__).parent / "descriptor.yaml"
_QUERIES_PATH = Path(__file__).parent / "queries.yaml"


def _load_descriptor() -> PlatformDescriptor:
    with open(_DESCRIPTOR_PATH, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return PlatformDescriptor(**data)


class B2BCenterAdapter(PlatformAdapter):
    def __init__(self) -> None:
        self._descriptor = _load_descriptor()

    def platform_id(self) -> str:
        return "b2bcenter"

    async def authenticate(self, credentials: PlatformCredentials) -> AuthSession:
        # Load saved session from manual login (scripts/b2bcenter_login.py)
        from pathlib import Path
        import json
        state_path = Path("data/b2bcenter_state.json")
        if state_path.exists():
            state = json.loads(state_path.read_text(encoding="utf-8"))
            cookies = {c["name"]: c["value"] for c in state.get("cookies", [])}
            return AuthSession(platform="b2bcenter", cookies=cookies)
        return AuthSession(platform="b2bcenter")

    async def fetch_new(
        self,
        session: AuthSession,
        since: datetime | None,
        descriptor: PlatformDescriptor | None,
    ) -> list[RawTender]:
        scraper = B2BCenterScraper(self._descriptor, _QUERIES_PATH, cookies=session.cookies)
        return await scraper.fetch_new(since)

    def map_to_tender(
        self, raw: RawTender, descriptor: PlatformDescriptor | None
    ) -> TenderModel:
        data = raw.raw
        tender_id = f"b2bcenter_{raw.external_id}"
        title = data.get("title", "").strip()
        if not title:
            raise ValueError(f"B2B-Center tender {raw.external_id} has empty title")
        url = data.get("url", "")
        if not url:
            raise ValueError(f"B2B-Center tender {raw.external_id} has no URL")

        buyer = data.get("buyer") or None
        budget = parse_price(data.get("budget_raw"))
        deadline = parse_deadline(data.get("deadline_raw"))

        return TenderModel(
            id=tender_id,
            platform="b2bcenter",
            external_id=raw.external_id,
            title=title,
            buyer=buyer,
            budget=budget,
            deadline=deadline,
            description=None,  # not available in listing
            url=url,
            raw_data=data,
            published_at=None,  # not available in listing
            status=TenderStatus.PENDING,
        )

    async def enrich_deadline(
        self,
        session: AuthSession,
        tender: TenderModel,
        descriptor: PlatformDescriptor | None,
    ) -> DeadlineExtractionOutcome:
        if tender.platform != "b2bcenter" or not tender.external_id.isdigit():
            return DeadlineExtractionOutcome(
                None,
                DeadlineExtractionState.EXTERNAL_FAILURE,
                DeadlineErrorCategory.INVALID_MARKUP,
            )
        url = (
            "https://www.b2b-center.ru/market/view.html?id="
            f"{tender.external_id}"
        )
        try:
            async with httpx.AsyncClient(
                headers=BROWSER_HEADERS,
                cookies=session.cookies,
                timeout=30.0,
                follow_redirects=True,
            ) as client:
                response = await client.get(url)
                if response.status_code == 404:
                    return DeadlineExtractionOutcome(
                        None,
                        DeadlineExtractionState.EXTERNAL_FAILURE,
                        DeadlineErrorCategory.NOT_FOUND,
                    )
                if response.status_code in (401, 403):
                    return DeadlineExtractionOutcome(
                        None,
                        DeadlineExtractionState.EXTERNAL_FAILURE,
                        DeadlineErrorCategory.UNAUTHORIZED,
                    )
                response.raise_for_status()
                return parse_detail_deadline(response.text)
        except httpx.TimeoutException:
            return DeadlineExtractionOutcome(
                None,
                DeadlineExtractionState.EXTERNAL_FAILURE,
                DeadlineErrorCategory.TIMEOUT,
            )
        except httpx.HTTPError:
            return DeadlineExtractionOutcome(
                None,
                DeadlineExtractionState.EXTERNAL_FAILURE,
                DeadlineErrorCategory.NETWORK_ERROR,
            )
