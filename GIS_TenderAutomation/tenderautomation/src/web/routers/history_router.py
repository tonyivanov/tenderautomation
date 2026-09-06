from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import Response
from fastapi.templating import Jinja2Templates

from core.models import HistoryFilters
from core.repositories import TenderRepository
from web.deps import require_user, _LoginRedirect

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))
_repo = TenderRepository()

PAGE_SIZE = 50


@router.get("/history")
async def history(
    request: Request,
    page: int = 1,
    platform: str | None = None,
    status: str | None = None,
    search: str | None = None,
) -> Response:
    try:
        user = require_user(request)
    except _LoginRedirect as e:
        return e.response

    offset = (max(page, 1) - 1) * PAGE_SIZE
    filters = HistoryFilters(
        platform=platform,
        status=status,
        search=search,
        limit=PAGE_SIZE + 1,
        offset=offset,
    )
    items = _repo.get_history(filters)
    has_next = len(items) > PAGE_SIZE
    items = items[:PAGE_SIZE]

    return templates.TemplateResponse(request, "history/list.html", {
        "current_user": user,
        "items": items,
        "page": page,
        "has_next": has_next,
        "filters": {"platform": platform, "status": status, "search": search},
    })
