"""Tenders list with V3 columns, tabs (P1/P2/Active/All), and deadline sorting."""
from __future__ import annotations

import sqlite3
from datetime import datetime as dt, timezone
from pathlib import Path
from typing import Any, TypedDict

from fastapi import APIRouter, Request
from fastapi.responses import Response
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from core.orm.user import TenderViewORM
from core.repositories import TenderRepository
from core.services.deadlines import is_expired
from web.deps import get_db, require_user, _LoginRedirect

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))

# Register format_analysis filter for deep analysis rendering
import re as _re
def _format_analysis(text: str) -> str:
    if not text:
        return ""
    html = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    html = _re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", html)
    html = _re.sub(r"(?:^|\n)(\d)\.\s*\*\*(.+?)\*\*", r"<div class='ai-section'><strong>\1. \2</strong></div>", html)
    html = _re.sub(r"(?:^|\n)\s*-\s+", "\n<li>", html)
    html = _re.sub(r"(<li>.*?</li>(?:\s*<li>.*?</li>)*)", r"<ul class='ai-list'>\1</ul>", html, flags=_re.DOTALL)
    return html.replace("\n", "<br>")

templates.env.filters["format_analysis"] = _format_analysis
_repo = TenderRepository()

PAGE_SIZE = 20
_CACHE_DB = Path(__file__).resolve().parent.parent.parent.parent / "data" / "cache" / "llm_classification_v3.db"

TABS = [
    ("P1", "🔥 P1 · Срочно"),
    ("P2", "📌 P2 · На проверку"),
    ("active", "🟢 Активные"),
    ("archive", "🗄 Архив"),
    ("taken", "✅ Взято"),
    ("deferred", "⏸ Отложено"),
    ("rejected", "❌ Отклонено"),
    ("all", "📋 Все"),
]


V3Item = dict[str, Any]


class _V3Cache(TypedDict):
    by_id: dict[str, V3Item]
    by_title: dict[str, V3Item]
    items: list[V3Item]


def _load_v3_cache() -> _V3Cache:
    if not _CACHE_DB.exists():
        return {"by_id": {}, "by_title": {}, "items": []}
    conn = sqlite3.connect(str(_CACHE_DB))
    conn.row_factory = sqlite3.Row
    try:
        columns = {r["name"] for r in conn.execute("PRAGMA table_info(classification_cache)")}
        if "tender_id" in columns:
            query = (
                "SELECT tender_id, normalized_title, verdict, fit_score, confidence, "
                "judge_verdict, judge_fit_score, judge_confidence, primary_domain "
                "FROM classification_cache"
            )
        else:
            query = (
                "SELECT NULL AS tender_id, normalized_title, verdict, fit_score, confidence, "
                "judge_verdict, judge_fit_score, judge_confidence, primary_domain "
                "FROM classification_cache"
            )
        rows = conn.execute(query).fetchall()
        result: _V3Cache = {"by_id": {}, "by_title": {}, "items": []}
        for r in rows:
            v = r["verdict"]
            fs = r["fit_score"]
            dom = r["primary_domain"] or ""
            jv = r["judge_verdict"]
            jfs = r["judge_fit_score"]
            jconf = r["judge_confidence"]
            if jv and jv != v and (jconf or 0) >= 0.70:
                v = jv
                fs = jfs
            if v == "core" and fs >= 85:
                q = "P1"
            elif v in ("core", "review"):
                q = "P2"
            else:
                q = "Reject"
            item = {
                "verdict": v, "fit_score": fs,
                "confidence": round(r["confidence"], 2) if r["confidence"] else 0,
                "queue": q, "domain": dom,
            }
            result["by_title"][r["normalized_title"]] = item
            if r["tender_id"]:
                result["by_id"][r["tender_id"]] = item
            result["items"].append(item)
        return result
    finally:
        conn.close()


def _tab_counts(v3: _V3Cache) -> dict[str, int]:
    counts = {"P1": 0, "P2": 0, "Reject": 0, "active": 0}
    for item in v3["items"]:
        q = item["queue"]
        if q in ("P1", "P2", "Reject"):
            counts[q] += 1
    # Active count is handled in the router (needs deadline data from DB)
    return counts


def _decorate_tenders(
    models: list[Any], v3_cache: _V3Cache, now: dt
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for tender in models:
        v3 = v3_cache["by_id"].get(tender.id) or v3_cache["by_title"].get(
            tender.title, {}
        )
        rows.append(
            {
                "id": tender.id,
                "title": tender.title,
                "platform": tender.platform,
                "buyer": tender.buyer,
                "budget": tender.budget,
                "deadline": tender.deadline,
                "status": tender.status,
                "url": tender.url,
                "v3_verdict": v3.get("verdict", ""),
                "v3_fit": v3.get("fit_score", 0),
                "v3_queue": v3.get("queue", ""),
                "v3_domain": v3.get("domain", ""),
                "expired": is_expired(tender.deadline, now),
            }
        )
    return rows


def _filter_search(
    rows: list[dict[str, Any]], search: str | None
) -> list[dict[str, Any]]:
    if not search:
        return rows
    needle = search.casefold()
    return [
        row
        for row in rows
        if needle in str(row.get("title") or "").casefold()
        or needle in str(row.get("buyer") or "").casefold()
    ]


def _is_review_queue_eligible(row: dict[str, Any]) -> bool:
    """Rejected tenders remain in history, but leave active review queues."""
    return bool(row["status"] != "rejected")


def _counts_for_rows(rows: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "P1": sum(
            1
            for row in rows
            if row["v3_queue"] == "P1"
            and not row["expired"]
            and _is_review_queue_eligible(row)
        ),
        "P2": sum(
            1
            for row in rows
            if row["v3_queue"] == "P2"
            and not row["expired"]
            and _is_review_queue_eligible(row)
        ),
        "active": sum(
            1
            for row in rows
            if row["v3_queue"] in ("P1", "P2")
            and row.get("deadline") is not None
            and not row["expired"]
            and _is_review_queue_eligible(row)
        ),
        "archive": sum(1 for row in rows if row["expired"]),
        "taken": sum(1 for row in rows if row["status"] == "taken"),
        "deferred": sum(1 for row in rows if row["status"] == "deferred"),
        "rejected": sum(1 for row in rows if row["status"] == "rejected"),
    }


def _filter_tab(
    rows: list[dict[str, Any]], tab: str
) -> list[dict[str, Any]]:
    if tab == "active":
        return [
            row
            for row in rows
            if row["v3_queue"] in ("P1", "P2")
            and row.get("deadline") is not None
            and not row["expired"]
            and _is_review_queue_eligible(row)
        ]
    if tab in ("P1", "P2"):
        return [
            row
            for row in rows
            if row["v3_queue"] == tab
            and not row["expired"]
            and _is_review_queue_eligible(row)
        ]
    if tab == "archive":
        return [row for row in rows if row["expired"]]
    if tab in ("taken", "deferred", "rejected"):
        return [row for row in rows if row["status"] == tab]
    return rows


def _sort_tenders(
    rows: list[dict[str, Any]], tab: str
) -> list[dict[str, Any]]:
    if tab == "archive":
        by_id = sorted(rows, key=lambda row: str(row["id"]))
        return sorted(by_id, key=lambda row: row["deadline"], reverse=True)

    def sort_key(row: dict[str, Any]) -> tuple[int, Any, str]:
        deadline = row.get("deadline")
        if not isinstance(deadline, dt) or (
            deadline.tzinfo is None or deadline.utcoffset() is None
        ):
            return (1, dt.max.replace(tzinfo=timezone.utc), str(row["id"]))
        if not row["expired"]:
            return (0, deadline.astimezone(timezone.utc), str(row["id"]))
        return (2, deadline.astimezone(timezone.utc), str(row["id"]))

    return sorted(rows, key=sort_key)


@router.get("/tenders")
async def list_tenders(
    request: Request,
    page: int = 1,
    platform: str | None = None,
    search: str | None = None,
    tab: str = "active",
) -> Response:
    try:
        user = require_user(request)
    except _LoginRedirect as e:
        return e.response

    v3_cache = _load_v3_cache()
    db: Session = next(get_db())
    try:
        from core.orm.tender import TenderORM
        from sqlalchemy import select as sa_select

        query = sa_select(TenderORM)
        if platform:
            query = query.where(TenderORM.platform == platform)
        query = query.order_by(TenderORM.deadline.desc().nulls_last()).limit(5000)
        rows = db.execute(query).scalars().all()
        all_models = [_repo.orm_to_model(r) for r in rows]

        now = dt.now(timezone.utc)
        all_tenders = _filter_search(
            _decorate_tenders(all_models, v3_cache, now), search
        )
        counts = _counts_for_rows(all_tenders)
        all_tenders = _sort_tenders(_filter_tab(all_tenders, tab), tab)

        # Paginate
        offset = (max(page, 1) - 1) * PAGE_SIZE
        tenders = all_tenders[offset:offset + PAGE_SIZE + 1]
        has_next = len(tenders) > PAGE_SIZE
        tenders = tenders[:PAGE_SIZE]

        # Viewed/unread
        tenders_ids = [t["id"] for t in tenders]
        viewed_ids = {
            row.tender_id
            for row in db.query(TenderViewORM)
            .filter(TenderViewORM.user_id == user.id)
            .filter(TenderViewORM.tender_id.in_(tenders_ids))
            .all()
        }
        is_new_map = {t["id"]: t["id"] not in viewed_ids for t in tenders}

        total_count = db.query(TenderORM).count()

        # Last collection info
        from core.orm.tender import CollectionRunORM
        from sqlalchemy import desc
        last_row = db.query(CollectionRunORM).filter(
            CollectionRunORM.status == "success"
        ).order_by(desc(CollectionRunORM.completed_at)).first()
        last_collection = {
            "at": last_row.completed_at.isoformat()[:19] if last_row and last_row.completed_at else "",
            "new_count": last_row.new_tenders_count if last_row else 0,
        }

        return templates.TemplateResponse(request, "tenders/list.html", {
            "current_user": user,
            "tenders": tenders,
            "is_new_map": is_new_map,
            "page": page,
            "has_next": has_next,
            "filters": {"platform": platform, "search": search or "", "tab": tab},
            "counts": counts,
            "total_count": total_count,
            "last_collection": last_collection,
            "tabs": TABS,
        })
    finally:
        db.close()


@router.get("/tenders/{tender_id}")
async def tender_detail(request: Request, tender_id: str) -> Response:
    try:
        user = require_user(request)
    except _LoginRedirect as e:
        return e.response

    tender = _repo.get_by_id(tender_id)
    if not tender:
        return templates.TemplateResponse(request, "errors/404.html", status_code=404)

    v3_cache = _load_v3_cache()
    v3_item = v3_cache["by_id"].get(tender.id) or v3_cache["by_title"].get(tender.title, {})

    db: Session = next(get_db())
    try:
        from sqlalchemy.dialects.postgresql import insert as pg_insert
        stmt = pg_insert(TenderViewORM).values(
            tender_id=tender_id, user_id=user.id
        ).on_conflict_do_nothing()
        db.execute(stmt)
        db.commit()

        from core.orm.tender import TenderActionORM
        ai_analysis = (
            db.query(TenderActionORM)
            .filter(TenderActionORM.tender_id == tender_id,
                    TenderActionORM.action_type == "ai_analysis")
            .order_by(TenderActionORM.created_at.desc())
            .first()
        )
        actions = (
            db.query(TenderActionORM)
            .filter(TenderActionORM.tender_id == tender_id)
            .order_by(TenderActionORM.created_at.desc())
            .all()
        )

        return templates.TemplateResponse(request, "tenders/detail.html", {
            "current_user": user,
            "tender": tender,
            "v3_info": v3_item,
            "ai_analysis": ai_analysis,
            "actions": actions,
            "ai_tier_options": ["⭐", "🟡", "🟠", "🔴"],
        })
    finally:
        db.close()
