"""Admin panel — run collection pipeline from web UI."""
from __future__ import annotations

import asyncio
import re
from pathlib import Path

from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from core.config import settings
from core.bootstrap import build_pipeline, build_reconciliation_service
from core.db import SessionLocal
from core.orm.tender import CollectionRunORM
from core.services import PipelineOrchestrator
from core.models import ReconciliationCommand, ReconciliationResult, ReconciliationSource
from sqlalchemy import select, desc

from web.deps import require_user, _LoginRedirect

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))

# Track running state
_collection_running = False
_collection_log: list[str] = []
_reconciliation_result: ReconciliationResult | None = None
_reconciliation_error: str | None = None
_COMMIT_SHA_RE = re.compile(r"^[0-9a-fA-F]{8,64}$")


def _short_commit_id(value: str | None) -> str:
    """Return a safe short commit SHA for the admin UI."""
    candidate = (value or "").strip()
    if not _COMMIT_SHA_RE.fullmatch(candidate):
        return "unknown"
    return candidate[:8].lower()


def _build_orchestrator() -> PipelineOrchestrator:
    """Reuse CLI pipeline builder."""
    from core.events import EventBus
    return build_pipeline(EventBus())


async def _run_pipeline_background() -> None:
    """Run collection + qualification in background."""
    global _collection_running, _collection_log
    from core.logging import get_logger
    log = get_logger("web.admin")

    try:
        orchestrator = _build_orchestrator()
        result = await orchestrator.run_async()
        _collection_log = [
            f"✅ Пайплайн завершён за {result.duration_sec:.0f} сек",
            f"📊 Новых тендеров: {result.collection.total_new}",
            f"🎯 Квалифицировано: {result.qualification.qualified_count}",
        ]
        log.info("web_pipeline_done", extra={"context": {
            "duration": result.duration_sec,
            "new_tenders": result.collection.total_new,
            "qualified": result.qualification.qualified_count,
        }})
    except Exception as exc:
        _collection_log = ["❌ Пайплайн завершился с ошибкой. Проверьте журнал приложения."]
        log.error("web_pipeline_error", extra={"context": {"error_type": type(exc).__name__}}, exc_info=True)
    finally:
        _collection_running = False


@router.get("/admin")
async def admin_panel(request: Request) -> Response:
    """Admin dashboard with collection runner."""
    try:
        user = require_user(request)
    except _LoginRedirect as e:
        return e.response

    # Only admin role
    if getattr(user, "role", "") != "admin":
        return RedirectResponse("/tenders", status_code=302)

    # Last 5 collection runs
    with SessionLocal() as session:
        runs = session.execute(
            select(CollectionRunORM).order_by(desc(CollectionRunORM.completed_at)).limit(10)
        ).scalars().all()
        run_history = [
            {"platform": r.platform, "status": r.status, "new": r.new_tenders_count,
             "updated": r.updated_tenders_count, "error": r.error_message,
             "at": r.completed_at.isoformat() if r.completed_at else ""}
            for r in runs
        ]

    # Total tender count + per-platform stats
    with SessionLocal() as session:
        from core.orm.tender import TenderORM
        total = session.query(TenderORM).count()
        b2b_count = session.query(TenderORM).filter(TenderORM.platform == "b2bcenter").count()
        bidzaar_count = session.query(TenderORM).filter(TenderORM.platform == "bidzaar").count()
        # Last successful per platform
        b2b_last = session.execute(
            select(CollectionRunORM).where(
                CollectionRunORM.platform == "b2bcenter",
                CollectionRunORM.status == "success"
            ).order_by(desc(CollectionRunORM.completed_at)).limit(1)
        ).scalar()
        bidzaar_last = session.execute(
            select(CollectionRunORM).where(
                CollectionRunORM.platform == "bidzaar",
                CollectionRunORM.status == "success"
            ).order_by(desc(CollectionRunORM.completed_at)).limit(1)
        ).scalar()

    return templates.TemplateResponse(request, "admin/panel.html", {
        "current_user": user,
        "commit_id": _short_commit_id(settings.app_commit_sha),
        "collection_running": _collection_running,
        "collection_log": _collection_log,
        "run_history": run_history,
        "total_tenders": total,
        "b2b_count": b2b_count,
        "bidzaar_count": bidzaar_count,
        "b2b_last_at": b2b_last.completed_at.isoformat()[:19] if b2b_last and b2b_last.completed_at else "",
        "bidzaar_last_at": bidzaar_last.completed_at.isoformat()[:19] if bidzaar_last and bidzaar_last.completed_at else "",
        "reconciliation_result": _reconciliation_result,
        "reconciliation_error": _reconciliation_error,
    })


@router.post("/admin/run-collection")
async def run_collection(request: Request) -> Response:
    """Trigger collection pipeline (admin only)."""
    try:
        user = require_user(request)
    except _LoginRedirect as e:
        return e.response

    if getattr(user, "role", "") != "admin":
        return RedirectResponse("/tenders", status_code=302)

    global _collection_running, _collection_log
    if _collection_running:
        return RedirectResponse("/admin?error=already_running", status_code=302)

    _collection_running = True
    _collection_log = ["⏳ Запуск пайплайна..."]
    try:
        asyncio.create_task(_run_pipeline_background())
    except Exception:
        _collection_running = False
        _collection_log = ["❌ Не удалось запланировать запуск пайплайна."]
        raise
    return RedirectResponse("/admin?started=1", status_code=302)


@router.post("/admin/reconcile-deadlines")
async def reconcile_deadlines(
    request: Request, batch_size: str = Form(default="50")
) -> Response:
    """Run one bounded reconciliation batch (admin only)."""
    try:
        user = require_user(request)
    except _LoginRedirect as exc:
        return exc.response
    if getattr(user, "role", "") != "admin":
        return RedirectResponse("/tenders", status_code=302)

    global _reconciliation_result, _reconciliation_error
    try:
        parsed_batch_size = int(batch_size)
        command = ReconciliationCommand(
            batch_size=parsed_batch_size,
            requested_by=str(getattr(user, "id", "admin")),
            source=ReconciliationSource.ADMIN,
        )
    except (TypeError, ValueError):
        _reconciliation_result = None
        _reconciliation_error = "Размер пакета должен быть целым числом от 1 до 200."
        return RedirectResponse("/admin?reconcile=invalid", status_code=303)

    try:
        _reconciliation_result = await build_reconciliation_service().run(command)
        _reconciliation_error = None
    except Exception as exc:
        _reconciliation_result = None
        _reconciliation_error = "Исправление не завершено. Проверьте журнал приложения."
        from core.logging import get_logger

        get_logger("web.admin").error(
            "deadline_reconciliation_failed",
            extra={"context": {"error_type": type(exc).__name__}},
            exc_info=True,
        )
    return RedirectResponse("/admin?reconcile=done", status_code=303)
