from __future__ import annotations

from pathlib import Path
import re

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from core.logging import get_logger
from web.middleware import SecurityHeadersMiddleware
from web.rate_limit import limiter
from web.routers import auth_router, tenders_router, actions_router, export_router, history_router, v3_router, admin_router, shortlist_router

log = get_logger("web.app")

_TEMPLATES_DIR = Path(__file__).parent / "templates"
_STATIC_DIR = Path(__file__).parent / "static"

templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))


def _format_analysis(text: str) -> str:
    """Convert DeepSeek analysis text to formatted HTML."""
    if not text:
        return ""
    # Escape HTML
    html = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    # Bold: **text**
    html = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", html)
    # Section headers: "1. **Заголовок**" or "**1. Заголовок:**"
    html = re.sub(r"(?:^|\n)(\d)\.\s*\*\*(.+?)\*\*", r"<div class='ai-section'><strong>\1. \2</strong></div>", html)
    # Bullet points: "- текст" → <li>
    html = re.sub(r"(?:^|\n)\s*-\s+", "\n<li>", html)
    # Wrap <li> sequences in <ul>
    html = re.sub(r"(<li>.*?</li>(?:\s*<li>.*?</li>)*)", r"<ul class='ai-list'>\1</ul>", html, flags=re.DOTALL)
    # Line breaks
    html = html.replace("\n", "<br>")
    return html


templates.env.filters["format_analysis"] = _format_analysis


def create_app() -> FastAPI:
    app = FastAPI(
        title="TenderAutomation",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )

    # Middleware
    app.add_middleware(SecurityHeadersMiddleware)

    # Rate limiting
    app.state.limiter = limiter

    async def rate_limit_handler(request: Request, exc: Exception) -> Response:
        if not isinstance(exc, RateLimitExceeded):
            raise exc
        return _rate_limit_exceeded_handler(request, exc)

    app.add_exception_handler(RateLimitExceeded, rate_limit_handler)

    # Global error handlers (SECURITY-15)
    @app.exception_handler(Exception)
    async def global_error_handler(request: Request, exc: Exception) -> HTMLResponse:
        log.error("unhandled_exception", extra={
            "context": {"path": str(request.url), "error": type(exc).__name__}
        })
        return templates.TemplateResponse(
            request,
            "errors/500.html", status_code=500
        )

    @app.exception_handler(404)
    async def not_found_handler(request: Request, exc: Exception) -> HTMLResponse:
        return templates.TemplateResponse(
            request,
            "errors/404.html", status_code=404
        )

    # Static files (served by Nginx in prod, FastAPI in dev)
    if _STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")

    # Routers
    app.include_router(auth_router.router)
    app.include_router(tenders_router.router)
    app.include_router(actions_router.router)
    app.include_router(export_router.router)
    app.include_router(history_router.router)
    app.include_router(v3_router.router)
    app.include_router(admin_router.router)
    app.include_router(shortlist_router.router)

    # Root redirect → login
    @app.get("/")
    async def root() -> RedirectResponse:
        return RedirectResponse("/login", status_code=302)

    return app


app = create_app()
