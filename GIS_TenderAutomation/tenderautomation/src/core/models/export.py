from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

if TYPE_CHECKING:
    from core.models.tender import TenderModel


class ProcedureState(str, Enum):
    UNKNOWN = "unknown"
    ACTIVE = "active"
    CLOSED = "closed"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    NOT_FOUND = "not_found"


class InspectionSource(str, Enum):
    UNKNOWN = "unknown"
    API = "api"
    ENDPOINT = "endpoint"
    PLAYWRIGHT = "playwright"
    DETAIL = "detail"


class InspectionErrorCategory(str, Enum):
    AUTH = "auth"
    TIMEOUT = "timeout"
    NETWORK = "network"
    NOT_FOUND = "not_found"
    PARSE = "parse"
    CONTRACT = "contract"
    STORAGE = "storage"
    CANCELLED = "cancelled"
    UNKNOWN = "unknown"


class V3LookupState(str, Enum):
    FOUND = "found"
    NOT_FOUND = "not_found"
    UNAVAILABLE = "unavailable"


class ExportOutcomeCategory(str, Enum):
    READY = "ready"
    ARCHIVE = "archive"
    INELIGIBLE = "ineligible"
    UNVERIFIED = "unverified"
    MISSING = "missing"


class InspectionApplyStatus(str, Enum):
    APPLIED = "applied"
    IDEMPOTENT = "idempotent"
    STALE = "stale"
    CONFLICT = "conflict"
    MISSING = "missing"


PROVENANCE_KEYS = frozenset(
    {
        "procedure_id",
        "procedure_status",
        "published_at_text",
        "deadline_text",
        "buyer_text",
        "budget_text",
        "inspection_mode",
        "source_url",
        "http_status",
        "detail_available",
        "documents_available",
        "page_kind",
        "schema_version",
        "endpoint_version",
        "captcha_detected",
        "login_required",
    }
)
MAX_PROVENANCE_KEYS = 16
MAX_PROVENANCE_BYTES = 8 * 1024


def _aware(value: datetime, field_name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")
    return value


class TenderInspectionResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    tender_id: str = Field(min_length=1, max_length=255)
    state: ProcedureState = ProcedureState.UNKNOWN
    verified: bool = False
    attempted_at: datetime
    source: InspectionSource = InspectionSource.UNKNOWN
    buyer: str | None = None
    budget: Decimal | None = None
    deadline: datetime | None = None
    description: str | None = None
    published_at: datetime | None = None
    raw_data_updates: dict[str, str | int | float | bool | None] = Field(
        default_factory=dict
    )
    error_category: InspectionErrorCategory | None = None

    @field_validator("attempted_at")
    @classmethod
    def validate_attempted_at(cls, value: datetime) -> datetime:
        return _aware(value, "attempted_at")

    @field_validator("deadline", "published_at")
    @classmethod
    def validate_optional_timestamp(cls, value: datetime | None) -> datetime | None:
        return _aware(value, "timestamp") if value is not None else None

    @field_validator("raw_data_updates")
    @classmethod
    def validate_provenance(
        cls, value: dict[str, str | int | float | bool | None]
    ) -> dict[str, str | int | float | bool | None]:
        if len(value) > MAX_PROVENANCE_KEYS:
            raise ValueError("provenance has too many keys")
        if not set(value).issubset(PROVENANCE_KEYS):
            raise ValueError("provenance contains unsupported keys")
        encoded = json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        if len(encoded) > MAX_PROVENANCE_BYTES:
            raise ValueError("provenance exceeds 8 KiB")
        return value

    @model_validator(mode="after")
    def validate_consistency(self) -> TenderInspectionResult:
        if self.verified and self.error_category is not None:
            raise ValueError("verified inspection cannot contain an error category")
        if not self.verified and self.state is not ProcedureState.UNKNOWN:
            raise ValueError("unverified inspection must use unknown state")
        return self


class InspectionApplyResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    tender_id: str
    status: InspectionApplyStatus
    business_changed: bool = False


class V3ExportContext(BaseModel):
    model_config = ConfigDict(frozen=True)

    tender_id: str | None = None
    title: str | None = None
    verdict: str | None = None
    fit_score: int | None = None
    confidence: float | None = None
    queue: str | None = None
    procurement_type: str | None = None


class V3LookupResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    state: V3LookupState
    context: V3ExportContext | None = None

    @model_validator(mode="after")
    def validate_context(self) -> V3LookupResult:
        if (self.state is V3LookupState.FOUND) != (self.context is not None):
            raise ValueError("found V3 lookup requires context")
        return self


class V3CandidateRef(BaseModel):
    model_config = ConfigDict(frozen=True)

    tender_id: str | None = None
    title: str | None = None


class ExportRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    tender_ids: tuple[str, ...] | None = None
    requested_at: datetime
    limit: int = Field(default=50, ge=1, le=50)

    @field_validator("requested_at")
    @classmethod
    def validate_requested_at(cls, value: datetime) -> datetime:
        return _aware(value, "requested_at")

    @field_validator("tender_ids")
    @classmethod
    def deduplicate_ids(cls, value: tuple[str, ...] | None) -> tuple[str, ...] | None:
        if value is None:
            return None
        normalized = tuple(dict.fromkeys(item.strip() for item in value if item.strip()))
        if not normalized or len(normalized) > 50:
            raise ValueError("tender_ids must contain between 1 and 50 unique IDs")
        if any(len(item) > 255 for item in normalized):
            raise ValueError("tender ID exceeds 255 characters")
        return normalized


class PreparedTender(BaseModel):
    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    tender: TenderModel
    v3: V3ExportContext | None = None
    completeness_warnings: tuple[str, ...] = ()


class ExportOutcome(BaseModel):
    model_config = ConfigDict(frozen=True)

    tender_id: str
    category: ExportOutcomeCategory
    prepared: PreparedTender | None = None
    reason: str


class ExportPreparationSummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    requested: int
    ready: int
    archive: int
    ineligible: int
    unverified: int
    missing: int


class ExportPreparationResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    outcomes: tuple[ExportOutcome, ...]
    summary: ExportPreparationSummary
