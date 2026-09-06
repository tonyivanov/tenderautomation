from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, computed_field

from .export import InspectionErrorCategory, InspectionSource, ProcedureState


class TenderStatus(str, Enum):
    PENDING = "pending"
    QUALIFIED = "qualified"
    FILTERED = "filtered"
    IN_REVIEW = "in_review"
    TAKEN = "taken"
    REJECTED = "rejected"
    DEFERRED = "deferred"

    def can_transition_to(self, target: "TenderStatus") -> bool:
        return target in _VALID_TRANSITIONS.get(self, set())


_VALID_TRANSITIONS: dict[TenderStatus, set[TenderStatus]] = {
    TenderStatus.PENDING: {TenderStatus.QUALIFIED, TenderStatus.FILTERED},
    TenderStatus.QUALIFIED: {TenderStatus.IN_REVIEW},
    TenderStatus.FILTERED: set(),
    TenderStatus.IN_REVIEW: {
        TenderStatus.TAKEN,
        TenderStatus.REJECTED,
        TenderStatus.DEFERRED,
    },
    TenderStatus.TAKEN: set(),
    TenderStatus.REJECTED: set(),
    TenderStatus.DEFERRED: {TenderStatus.IN_REVIEW},
}


def _normalize(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip().lower()
    if isinstance(value, Decimal):
        return f"{value:.2f}"
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    return str(value).strip().lower()


def compute_content_hash(
    title: str,
    buyer: str | None,
    budget: Decimal | None,
    deadline: datetime | None,
    description: str | None,
) -> str:
    normalized = {
        "title": _normalize(title),
        "buyer": _normalize(buyer),
        "budget": _normalize(budget),
        "deadline": _normalize(deadline),
        "description": _normalize(description),
    }
    payload = json.dumps(normalized, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class RawTender(BaseModel):
    platform: str
    external_id: str
    raw: dict[str, Any]


class TenderModel(BaseModel):
    id: str  # {platform}_{external_id}
    platform: str
    external_id: str
    title: str
    buyer: str | None = None
    budget: Decimal | None = None
    deadline: datetime | None = None
    description: str | None = None
    url: str
    raw_data: dict[str, Any] = Field(default_factory=dict)
    content_hash: str = ""
    prefilter_score: int = 0
    qualification_tier: str | None = None
    matched_keywords: list[str] = Field(default_factory=list)
    status: TenderStatus = TenderStatus.PENDING
    published_at: datetime | None = None
    collected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    procedure_state: ProcedureState = ProcedureState.UNKNOWN
    procedure_checked_at: datetime | None = None
    procedure_last_attempt_at: datetime | None = None
    procedure_source: InspectionSource | None = None
    procedure_error_category: InspectionErrorCategory | None = None

    def model_post_init(self, __context: Any) -> None:
        if not self.content_hash:
            self.content_hash = compute_content_hash(
                self.title, self.buyer, self.budget, self.deadline, self.description
            )

    def to_jsonl_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "platform": self.platform,
            "title": self.title,
            "buyer": self.buyer,
            "budget": str(self.budget) if self.budget is not None else None,
            "deadline": self.deadline.isoformat() if self.deadline else None,
            "url": self.url,
            "description": self.description,
            "prefilter_score": self.prefilter_score,
            "qualification_tier": self.qualification_tier,
            "matched_keywords": self.matched_keywords,
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "exported_at": datetime.now(timezone.utc).isoformat(),
        }


class ScoredTender(BaseModel):
    tender: TenderModel
    score: int
    matched_keywords: list[str]
    tier: str  # "qualified" | "filtered"


class CollectionResult(BaseModel):
    platform: str
    new_count: int = 0
    updated_count: int = 0
    skipped_count: int = 0
    failed_count: int = 0
    error: str | None = None
    success: bool = True
