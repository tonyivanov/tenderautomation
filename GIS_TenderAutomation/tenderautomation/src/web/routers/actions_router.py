from __future__ import annotations

from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse, Response
from pydantic import BaseModel, Field

from core.logging import get_logger
from core.models import AnalysisResult, TenderAction
from core.repositories import ActionLogRepository, TenderRepository
from core.config import settings
from web.deps import require_user, _LoginRedirect

log = get_logger(__name__)
router = APIRouter()

_tender_repo = TenderRepository()
_action_log = ActionLogRepository(settings.data_dir)

VALID_ACTIONS = {"taken", "rejected", "deferred"}
VALID_TIERS = {"⭐", "🟡", "🟠", "🔴"}


@router.post("/tenders/{tender_id}/action")
@router.get("/tenders/{tender_id}/action")
async def record_action(
    request: Request,
    tender_id: str,
    action: str = "",
    notes: str = "",
) -> Response:
    try:
        user = require_user(request)
    except _LoginRedirect as e:
        return e.response

    # Get action from query params (GET) or form data (POST)
    if not action:
        action = request.query_params.get("action", "")
    if not notes:
        # Try form data for POST
        try:
            form = await request.form()
            if not action:
                action = form.get("action", "")
            if not notes:
                notes = form.get("notes", "")
        except Exception:
            pass

    if action not in VALID_ACTIONS and action not in ("notes", "clear"):
        return RedirectResponse(f"/tenders/{tender_id}", status_code=303)

    notes_clean = notes.strip()[:500] if notes else None

    # Clear status → back to original
    if action == "clear":
        action_type = "clear"
        _tender_repo.set_status(tender_id, "filtered")
    elif action == "notes":
        action_type = "note"
    else:
        action_type = action
        _tender_repo.set_status(tender_id, action)

    tender_action = TenderAction(
        id=uuid4(),
        tender_id=tender_id,
        action_type=action_type,
        user_id=str(user.id),
        notes=notes_clean,
    )
    _tender_repo.save_action(tender_action)
    _action_log.append(tender_action)

    log.info("action_recorded", extra={"context": {
        "tender_id": tender_id, "action": action_type, "user": user.username
    }})
    return RedirectResponse(f"/tenders/{tender_id}", status_code=303)


@router.post("/tenders/{tender_id}/analysis")
async def upload_analysis(
    request: Request,
    tender_id: str,
    ai_tier: str = Form(...),
    ai_rationale: str = Form(...),
    ai_tool: str = Form(default=""),
) -> Response:
    try:
        user = require_user(request)
    except _LoginRedirect as e:
        return e.response

    if ai_tier not in VALID_TIERS:
        return RedirectResponse(f"/tenders/{tender_id}", status_code=303)

    rationale = ai_rationale.strip()
    if not rationale or len(rationale) > 2000:
        return RedirectResponse(f"/tenders/{tender_id}", status_code=303)

    analysis = AnalysisResult(
        ai_tier=ai_tier,
        ai_rationale=rationale,
        ai_tool=ai_tool.strip()[:100] or None,
    )
    _tender_repo.save_analysis(tender_id, analysis, user_id=str(user.id))
    return RedirectResponse(f"/tenders/{tender_id}", status_code=303)


@router.post("/tenders/{tender_id}/deep-analysis")
async def deep_analysis(request: Request, tender_id: str) -> Response:
    """Auto-analyze tender: scrape description + LLM analysis."""
    try:
        user = require_user(request)
    except _LoginRedirect as e:
        return e.response

    tender = _tender_repo.get_by_id(tender_id)
    if not tender:
        return RedirectResponse("/tenders", status_code=303)

    import asyncio
    from core.services.scoring_v3.deep_analyzer import analyze_tender

    try:
        result = await analyze_tender(
            title=tender.title,
            url=tender.url,
            buyer=tender.buyer or "",
            budget=str(tender.budget) if tender.budget else "",
            deadline=tender.deadline.isoformat() if tender.deadline else "",
            platform=tender.platform,
        )
        analysis = AnalysisResult(
            ai_tier=result.tier,
            ai_rationale=result.rationale[:2000],
            ai_tool=result.tool,
        )
        _tender_repo.save_analysis(tender_id, analysis, user_id=str(user.id))
    except Exception as e:
        log.error("deep_analysis_failed", extra={"context": {"tender_id": tender_id, "error": str(e)}})
        # Save error as analysis
        analysis = AnalysisResult(
            ai_tier="🟠",
            ai_rationale=f"Ошибка автоматического анализа: {str(e)[:500]}",
            ai_tool="DeepSeek V4 (error)",
        )
        _tender_repo.save_analysis(tender_id, analysis, user_id=str(user.id))

    return RedirectResponse(f"/tenders/{tender_id}", status_code=303)
