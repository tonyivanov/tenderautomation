from __future__ import annotations

import re
from datetime import datetime, time, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from core.models import (
    DeadlineCandidate,
    DeadlineExtractionOutcome,
    DeadlineExtractionState,
    DeadlineLabelKind,
    DeadlineSource,
    NormalizedDeadline,
)

_DATE_ONLY_PATTERNS = (
    (re.compile(r"^\d{2}\.\d{2}\.\d{4}$"), "%d.%m.%Y"),
    (re.compile(r"^\d{4}-\d{2}-\d{2}$"), "%Y-%m-%d"),
)
_LOCAL_DATETIME_FORMATS = (
    "%d.%m.%Y %H:%M",
    "%d.%m.%Y %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%Y-%m-%d %H:%M:%S",
)
_DATE_VALUE_RE = re.compile(
    r"(?:\d{2}\.\d{2}\.\d{4}(?:\s+\d{1,2}:\d{2}(?::\d{2})?)?"
    r"|\d{4}-\d{2}-\d{2}(?:[T\s]\d{1,2}:\d{2}(?::\d{2})?(?:Z|[+-]\d{2}:\d{2})?)?)"
)
_ACCEPTANCE_LABEL_RE = re.compile(
    r"окончани[ея]\s+при[её]ма\s+(?:заявок|предложений)|"
    r"при[её]м\s+(?:заявок|предложений)\s+до|"
    r"acceptance\s+end|deadline",
    re.I,
)
_TRADING_LABEL_RE = re.compile(
    r"дата\s+торгов|проведени[ея]\s+аукциона|auction\s+date",
    re.I,
)


def _timezone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"Unknown platform timezone: {name}") from exc


def parse_deadline_value(
    text: str | None,
    *,
    timezone_name: str = "Europe/Moscow",
) -> tuple[datetime, bool] | None:
    """Strictly parse a supported value and normalize it to aware UTC."""
    if not text:
        return None
    clean = text.strip()
    if not clean or len(clean) > 100:
        return None

    local_tz = _timezone(timezone_name)
    for pattern, fmt in _DATE_ONLY_PATTERNS:
        if pattern.fullmatch(clean):
            try:
                local_date = datetime.strptime(clean, fmt).date()
            except ValueError:
                return None
            local_value = datetime.combine(
                local_date, time(23, 59, 59), tzinfo=local_tz
            )
            return local_value.astimezone(timezone.utc), True

    iso_value = clean.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(iso_value)
    except ValueError:
        parsed = None
    if parsed is not None:
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            parsed = parsed.replace(tzinfo=local_tz)
        return parsed.astimezone(timezone.utc), False

    for fmt in _LOCAL_DATETIME_FORMATS:
        try:
            parsed = datetime.strptime(clean, fmt).replace(tzinfo=local_tz)
        except ValueError:
            continue
        return parsed.astimezone(timezone.utc), False
    return None


def normalize_deadline(
    text: str | None,
    *,
    source: DeadlineSource,
    timezone_name: str = "Europe/Moscow",
    label_kind: DeadlineLabelKind | None = None,
) -> NormalizedDeadline | None:
    parsed = parse_deadline_value(text, timezone_name=timezone_name)
    if parsed is None:
        return None
    value, date_only = parsed
    return NormalizedDeadline(
        value=value,
        source=source,
        label_kind=label_kind,
        date_only=date_only,
    )


def make_candidate(
    raw_text: str,
    *,
    source: DeadlineSource,
    label_kind: DeadlineLabelKind | None,
    priority: int,
    timezone_name: str = "Europe/Moscow",
) -> DeadlineCandidate:
    bounded = raw_text.strip()[:500]
    parsed = parse_deadline_value(bounded, timezone_name=timezone_name)
    return DeadlineCandidate(
        raw_text=bounded,
        source=source,
        label_kind=label_kind,
        priority=priority,
        parsed_value=parsed[0] if parsed else None,
        date_only=parsed[1] if parsed else False,
    )


def resolve_deadline_candidates(
    candidates: list[DeadlineCandidate],
) -> DeadlineExtractionOutcome:
    if not candidates:
        return DeadlineExtractionOutcome(
            deadline=None, state=DeadlineExtractionState.MISSING
        )

    valid = [
        candidate
        for candidate in candidates
        if candidate.label_kind is not None and candidate.parsed_value is not None
    ]
    if not valid:
        return DeadlineExtractionOutcome(
            deadline=None, state=DeadlineExtractionState.INVALID
        )

    priority = min(candidate.priority for candidate in valid)
    selected = [candidate for candidate in valid if candidate.priority == priority]
    distinct_values = {candidate.parsed_value for candidate in selected}
    if len(distinct_values) != 1:
        return DeadlineExtractionOutcome(
            deadline=None, state=DeadlineExtractionState.AMBIGUOUS
        )

    winner = selected[0]
    parsed_value = winner.parsed_value
    if parsed_value is None:
        return DeadlineExtractionOutcome(
            deadline=None, state=DeadlineExtractionState.INVALID
        )
    return DeadlineExtractionOutcome(
        deadline=NormalizedDeadline(
            value=parsed_value.astimezone(timezone.utc),
            source=winner.source,
            label_kind=winner.label_kind,
            date_only=winner.date_only,
        ),
        state=DeadlineExtractionState.RESOLVED,
    )


def resolve_labeled_deadline_lines(
    lines: list[str],
    *,
    timezone_name: str = "Europe/Moscow",
) -> DeadlineExtractionOutcome:
    """Resolve explicit acceptance/trading labels from normalized page text lines."""
    candidates: list[DeadlineCandidate] = []
    clean_lines = [line.strip() for line in lines if line.strip()]
    for index, line in enumerate(clean_lines):
        label_kind: DeadlineLabelKind | None = None
        priority = 0
        if _ACCEPTANCE_LABEL_RE.search(line):
            label_kind = DeadlineLabelKind.ACCEPTANCE_END
            priority = 1
        elif _TRADING_LABEL_RE.search(line):
            label_kind = DeadlineLabelKind.TRADING_DATE
            priority = 2
        if label_kind is None:
            continue

        search_text = line
        if not _DATE_VALUE_RE.search(search_text) and index + 1 < len(clean_lines):
            next_line = clean_lines[index + 1]
            if not (
                _ACCEPTANCE_LABEL_RE.search(next_line)
                or _TRADING_LABEL_RE.search(next_line)
            ):
                search_text = f"{line} {next_line}"
        match = _DATE_VALUE_RE.search(search_text)
        if match:
            candidates.append(
                make_candidate(
                    match.group(0),
                    source=DeadlineSource.DETAIL,
                    label_kind=label_kind,
                    priority=priority,
                    timezone_name=timezone_name,
                )
            )
    return resolve_deadline_candidates(candidates)


def provenance(outcome: DeadlineExtractionOutcome) -> dict[str, object]:
    if outcome.deadline is None:
        return {
            "deadline_source": DeadlineSource.UNRESOLVED.value,
            "deadline_label_kind": None,
        }
    return {
        "deadline_source": outcome.deadline.source.value,
        "deadline_label_kind": (
            outcome.deadline.label_kind.value
            if outcome.deadline.label_kind is not None
            else None
        ),
        "deadline_date_only": outcome.deadline.date_only,
    }


def is_expired(deadline: datetime | None, now_utc: datetime | None = None) -> bool:
    if deadline is None or deadline.tzinfo is None or deadline.utcoffset() is None:
        return False
    now = now_utc or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now_utc must be timezone-aware")
    return deadline.astimezone(timezone.utc) < now.astimezone(timezone.utc)
