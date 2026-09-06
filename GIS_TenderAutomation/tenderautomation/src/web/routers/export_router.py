from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import Response, StreamingResponse

from core.repositories import TenderRepository
from web.deps import require_user, _LoginRedirect
from web.services.export import ExportService

router = APIRouter()
_export_svc = ExportService(TenderRepository())


@router.get("/export/zip")
async def export_zip(request: Request, ids: str | None = None) -> Response:
    try:
        require_user(request)
    except _LoginRedirect as e:
        return e.response

    tender_ids = [i.strip() for i in ids.split(",") if i.strip()] if ids else None
    zip_buf = _export_svc.build_zip(tender_ids)

    from datetime import datetime, timezone
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    filename = f"tender_export_{date_str}.zip"

    return StreamingResponse(
        zip_buf,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
