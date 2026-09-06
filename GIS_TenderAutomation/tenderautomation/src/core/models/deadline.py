from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class DeadlineSource(str, Enum):
    LISTING = "listing"
    API = "api"
    DETAIL = "detail"
    UNRESOLVED = "unresolved"


class DeadlineLabelKind(str, Enum):
    ACCEPTANCE_END = "acceptance_end"
    TRADING_DATE = "trading_date"


class DeadlineExtractionState(str, Enum):
    RESOLVED = "resolved"
    MISSING = "missing"
    INVALID = "invalid"
    AMBIGUOUS = "ambiguous"
    EXTERNAL_FAILURE = "external_failure"


class DeadlineErrorCategory(str, Enum):
    TIMEOUT = "timeout"
    NOT_FOUND = "not_found"
    UNAUTHORIZED = "unauthorized"
    CAPTCHA = "captcha"
    INVALID_MARKUP = "invalid_markup"
    NETWORK_ERROR = "network_error"


class ReconciliationSource(str, Enum):
    ADMIN = "admin"
    CLI = "cli"


@dataclass(frozen=True)
class NormalizedDeadline:
    value: datetime
    source: DeadlineSource
    label_kind: DeadlineLabelKind | None = None
    date_only: bool = False

    def __post_init__(self) -> None:
        if self.value.tzinfo is None or self.value.utcoffset() is None:
            raise ValueError("NormalizedDeadline.value must be timezone-aware")
        if self.source is DeadlineSource.UNRESOLVED:
            raise ValueError("A normalized deadline cannot have an unresolved source")


@dataclass(frozen=True, repr=False)
class DeadlineCandidate:
    raw_text: str
    source: DeadlineSource
    label_kind: DeadlineLabelKind | None
    priority: int
    parsed_value: datetime | None
    date_only: bool = False

    def __post_init__(self) -> None:
        if len(self.raw_text) > 500:
            raise ValueError("Deadline candidate text exceeds 500 characters")
        if self.parsed_value is not None and (
            self.parsed_value.tzinfo is None
            or self.parsed_value.utcoffset() is None
        ):
            raise ValueError("DeadlineCandidate.parsed_value must be timezone-aware")


@dataclass(frozen=True)
class DeadlineExtractionOutcome:
    deadline: NormalizedDeadline | None
    state: DeadlineExtractionState
    error_category: DeadlineErrorCategory | None = None

    def __post_init__(self) -> None:
        if self.state is DeadlineExtractionState.RESOLVED and self.deadline is None:
            raise ValueError("A resolved outcome requires a deadline")
        if self.deadline is not None and self.state is not DeadlineExtractionState.RESOLVED:
            raise ValueError("Only a resolved outcome may contain a deadline")
        if (
            self.state is DeadlineExtractionState.EXTERNAL_FAILURE
            and self.error_category is None
        ):
            raise ValueError("External failure requires a safe error category")
        if (
            self.state is not DeadlineExtractionState.EXTERNAL_FAILURE
            and self.error_category is not None
        ):
            raise ValueError("Only external failure may contain an error category")


@dataclass(frozen=True)
class ReconciliationCommand:
    batch_size: int = 50
    requested_by: str = "system"
    source: ReconciliationSource = ReconciliationSource.CLI

    def __post_init__(self) -> None:
        if isinstance(self.batch_size, bool) or not 1 <= self.batch_size <= 200:
            raise ValueError("batch_size must be between 1 and 200")
        if not self.requested_by.strip():
            raise ValueError("requested_by must not be empty")


@dataclass
class ReconciliationResult:
    scanned: int = 0
    deadline_updated: int = 0
    url_updated: int = 0
    unresolved: int = 0
    failed: int = 0
    remaining_candidates: int = 0
    already_running: bool = False

    def __post_init__(self) -> None:
        counters = (
            self.scanned,
            self.deadline_updated,
            self.url_updated,
            self.unresolved,
            self.failed,
            self.remaining_candidates,
        )
        if any(value < 0 for value in counters):
            raise ValueError("Reconciliation counters must be nonnegative")
