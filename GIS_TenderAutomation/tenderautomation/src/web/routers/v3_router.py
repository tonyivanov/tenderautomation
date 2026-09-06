"""V3 classification dashboard — P1/P2/P3 queues from LLM cache + PostgreSQL."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import Response
from fastapi.templating import Jinja2Templates

from web.deps import require_user, _LoginRedirect

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))

_CACHE_DB = Path(__file__).resolve().parent.parent.parent.parent / "data" / "cache" / "llm_classification_v3.db"


def _read_v3_cache() -> list[dict[str, Any]]:
    """Read all cached classifications with judge data."""
    if not _CACHE_DB.exists():
        return []
    conn = sqlite3.connect(str(_CACHE_DB))
    conn.row_factory = sqlite3.Row
    try:
        columns = {r["name"] for r in conn.execute("PRAGMA table_info(classification_cache)")}
        if "tender_id" in columns:
            query = """
                SELECT cache_key, tender_id, normalized_title, verdict, fit_score,
                       confidence, procurement_type, primary_domain, reason,
                       judge_verdict, judge_fit_score, judge_confidence,
                       model_used, estimated_cost, created_at
                FROM classification_cache
                ORDER BY created_at DESC
            """
        else:
            query = """
                SELECT cache_key, NULL AS tender_id, normalized_title, verdict, fit_score,
                       confidence, procurement_type, primary_domain, reason,
                       judge_verdict, judge_fit_score, judge_confidence,
                       model_used, estimated_cost, created_at
                FROM classification_cache
                ORDER BY created_at DESC
            """
        rows = conn.execute(query).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def _match_tender(
    row: dict[str, Any],
    by_id: dict[str, Any],
    by_title: dict[str, list[Any]],
) -> Any | None:
    if row.get("tender_id") in by_id:
        return by_id[row["tender_id"]]
    matches = by_title.get(row.get("normalized_title", ""), [])
    return matches[0] if len(matches) == 1 else None


def _enrich_with_pg(cache_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Join by stable ID, falling back to exact unambiguous legacy titles."""
    import time
    from core.db import SessionLocal
    from core.orm.tender import TenderORM
    from sqlalchemy import select

    t0 = time.perf_counter()
    enriched: list[dict[str, Any]] = []

    # Fetch ALL tenders from PG once (1,412 rows — cheap)
    with SessionLocal() as session:
        pg_rows = session.execute(select(TenderORM)).scalars().all()
        pg_by_id: dict[str, Any] = {}
        pg_by_title: dict[str, list[Any]] = {}
        for t in pg_rows:
            pg_by_id[t.id] = t
            pg_by_title.setdefault(t.title or "", []).append(t)

    for source_row in cache_rows:
        row = dict(source_row)
        pg_tender = _match_tender(row, pg_by_id, pg_by_title)

        row["url"] = pg_tender.url if pg_tender else ""
        row["buyer"] = pg_tender.buyer if pg_tender else ""
        row["budget"] = float(pg_tender.budget) if pg_tender and pg_tender.budget else 0
        row["deadline"] = pg_tender.deadline.isoformat() if pg_tender and pg_tender.deadline else ""
        row["platform"] = pg_tender.platform if pg_tender else ""
        row["tender_id"] = pg_tender.id if pg_tender else row.get("tender_id") or row["cache_key"][:16]
        row["status"] = pg_tender.status if pg_tender else "pending"
        enriched.append(row)

    elapsed = time.perf_counter() - t0
    import logging
    logging.getLogger(__name__).debug("_enrich_with_pg: %d rows in %.2f ms", len(enriched), elapsed * 1000)
    return enriched


def _assign_queue(row: dict[str, Any], post_filter: bool = True) -> str:
    """Determine final queue: P1, P2, P3, or Reject."""
    verdict = row.get("verdict", "review")
    judge_v = row.get("judge_verdict", "")
    fit = row.get("fit_score", 0)
    conf = row.get("confidence", 0.5)
    j_fit = row.get("judge_fit_score", 0)
    j_conf = row.get("judge_confidence", 0)
    proc_type = row.get("procurement_type", "unknown")
    domain = row.get("primary_domain", "unknown")

    effective_verdict = verdict
    effective_fit = fit
    if judge_v and judge_v != verdict:
        if j_conf >= 0.70:
            effective_verdict = judge_v
            effective_fit = j_fit

    if effective_verdict == "core" and effective_fit >= 85:
        if proc_type in ("services", "mixed"):
            return "P1"
    if effective_verdict == "core" or effective_verdict == "review":
        return "P2"
    if proc_type == "mixed":
        return "P2"
    if domain in ("non_it", "facilities", "web_and_marketing", "office_it"):
        return "Reject"
    return "Reject"


@router.get("/v3")
async def v3_dashboard(
    request: Request,
    queue: str = "all",
) -> Response:
    """V3 LLM classification dashboard with P1/P2/P3/Reject tabs."""
    try:
        user = require_user(request)
    except _LoginRedirect as e:
        return e.response

    cache_rows = _read_v3_cache()
    enriched = _enrich_with_pg(cache_rows)

    from datetime import datetime as dt, timezone
    now = dt.now(timezone.utc)

    for row in enriched:
        row["queue"] = _assign_queue(row)
        dl = row.get("deadline", "")
        if dl:
            try:
                row["expired"] = dt.fromisoformat(dl) < now
            except ValueError:
                row["expired"] = False
        else:
            row["expired"] = False

    # Sort: active (closest deadline first) → no deadline → expired
    def _sort_key(r: dict[str, Any]) -> tuple[int, str]:
        has_dl = bool(r.get("deadline"))
        active = has_dl and not r.get("expired", False)
        if active:
            return (0, r["deadline"])   # closest deadline first
        elif has_dl:
            return (2, r["deadline"])   # expired last
        else:
            return (1, "9999")          # no deadline in middle

    enriched.sort(key=_sort_key)

    # Pre-compute stats from FULL list (before filtering)
    stats = {q: len([r for r in enriched if r["queue"] == q]) for q in ["P1", "P2", "Reject"]}
    active_count = sum(1 for r in enriched if r["queue"] in ("P1","P2") and r.get("deadline") and not r.get("expired"))
    expired_count = sum(1 for r in enriched if r["queue"] in ("P1","P2") and r.get("deadline") and r.get("expired"))
    no_dl_count = sum(1 for r in enriched if r["queue"] in ("P1","P2") and not r.get("deadline"))

    # Filter: queue
    if queue != "all" and queue != "active":
        enriched = [r for r in enriched if r["queue"] == queue]
    elif queue == "active":
        # Active only: P1/P2 + has deadline + not expired
        enriched = [r for r in enriched
                    if r["queue"] in ("P1","P2")
                    and r.get("deadline")
                    and not r["expired"]]

    return templates.TemplateResponse(request, "v3/dashboard.html", {
        "current_user": user,
        "tenders": enriched,
        "queue": queue,
        "stats": stats,
        "total": len(cache_rows),
        "active_count": active_count,
        "expired_count": expired_count,
        "no_dl_count": no_dl_count,
    })
