"""Shortlist — redirect to /tenders?tab=taken."""
from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import RedirectResponse

router = APIRouter()


@router.get("/shortlist")
async def shortlist() -> RedirectResponse:
    return RedirectResponse("/tenders?tab=taken", status_code=302)
