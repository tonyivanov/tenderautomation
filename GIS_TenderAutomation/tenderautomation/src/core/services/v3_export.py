from __future__ import annotations

import sqlite3
from collections import defaultdict
from pathlib import Path

from core.models import (
    TenderModel,
    V3CandidateRef,
    V3ExportContext,
    V3LookupResult,
    V3LookupState,
)

DEFAULT_V3_CACHE_PATH = (
    Path(__file__).resolve().parents[3] / "data/cache/llm_classification_v3.db"
)
JUDGE_CONFIDENCE_THRESHOLD = 0.70


def resolve_queue(row: sqlite3.Row) -> V3ExportContext:
    keys = set(row.keys())
    verdict = str(row["verdict"] or "review")
    fit = int(row["fit_score"] or 0)
    confidence = float(row["confidence"] or 0.0)
    judge_verdict = str(row["judge_verdict"] or "") if "judge_verdict" in keys else ""
    judge_fit = int(row["judge_fit_score"] or 0) if "judge_fit_score" in keys else 0
    judge_conf = float(row["judge_confidence"] or 0.0) if "judge_confidence" in keys else 0.0
    procurement_type = (
        str(row["procurement_type"] or "unknown")
        if "procurement_type" in keys
        else "unknown"
    )
    if judge_verdict and judge_verdict != verdict and judge_conf >= JUDGE_CONFIDENCE_THRESHOLD:
        verdict, fit, confidence = judge_verdict, judge_fit, judge_conf
    if verdict == "core" and fit >= 85 and procurement_type in {"services", "mixed"}:
        queue = "P1"
    elif verdict in {"core", "review"} or procurement_type == "mixed":
        queue = "P2"
    else:
        queue = "Reject"
    return V3ExportContext(
        tender_id=(str(row["tender_id"]) if "tender_id" in keys and row["tender_id"] else None),
        title=str(row["normalized_title"]),
        verdict=verdict,
        fit_score=fit,
        confidence=confidence,
        queue=queue,
        procurement_type=procurement_type,
    )


class V3ExportProjection:
    def __init__(self, path: Path | str = DEFAULT_V3_CACHE_PATH, *, timeout: float = 1.0) -> None:
        self._path = Path(path)
        self._timeout = timeout

    def _read_rows(self) -> list[sqlite3.Row]:
        if not self._path.is_file():
            raise OSError("V3 cache unavailable")
        connection = sqlite3.connect(str(self._path), timeout=self._timeout)
        connection.row_factory = sqlite3.Row
        try:
            return connection.execute(
                "SELECT * FROM classification_cache ORDER BY created_at DESC, cache_key ASC"
            ).fetchall()
        finally:
            connection.close()

    def get_many(self, tenders: tuple[TenderModel, ...]) -> dict[str, V3LookupResult]:
        try:
            rows = self._read_rows()
        except (OSError, sqlite3.Error):
            return {
                tender.id: V3LookupResult(state=V3LookupState.UNAVAILABLE)
                for tender in tenders
            }
        by_id: dict[str, sqlite3.Row] = {}
        by_title: dict[str, list[sqlite3.Row]] = defaultdict(list)
        for row in rows:
            keys = set(row.keys())
            if "tender_id" in keys and row["tender_id"]:
                by_id.setdefault(str(row["tender_id"]), row)
            by_title[str(row["normalized_title"])].append(row)
        result: dict[str, V3LookupResult] = {}
        for tender in tenders:
            matched_row: sqlite3.Row | None = by_id.get(tender.id)
            if matched_row is None:
                title_rows = by_title.get(tender.title, [])
                matched_row = title_rows[0] if len(title_rows) == 1 else None
            result[tender.id] = (
                V3LookupResult(
                    state=V3LookupState.FOUND,
                    context=resolve_queue(matched_row),
                )
                if matched_row is not None
                else V3LookupResult(state=V3LookupState.NOT_FOUND)
            )
        return result

    def list_eligible_refs(self, *, limit: int = 50) -> tuple[V3CandidateRef, ...]:
        if isinstance(limit, bool) or not 1 <= limit <= 50:
            raise ValueError("limit must be between 1 and 50")
        try:
            rows = self._read_rows()
        except (OSError, sqlite3.Error):
            return ()
        refs: list[V3CandidateRef] = []
        seen: set[tuple[str | None, str | None]] = set()
        for row in rows:
            context = resolve_queue(row)
            if context.queue not in {"P1", "P2"}:
                continue
            key = (context.tender_id, context.title)
            if key not in seen:
                refs.append(V3CandidateRef(tender_id=context.tender_id, title=context.title))
                seen.add(key)
            if len(refs) == limit:
                break
        return tuple(refs)
