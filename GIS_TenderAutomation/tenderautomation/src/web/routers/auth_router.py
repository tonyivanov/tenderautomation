from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from core.logging import get_logger
from core.orm.user import LoginAttemptORM
from web.auth import create_session, get_user_by_username, verify_password
from web.deps import get_db, require_user, _LoginRedirect
from web.rate_limit import limiter

log = get_logger(__name__)
router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))


@router.get("/login")
async def login_page(request: Request) -> Response:
    response = templates.TemplateResponse(request, "auth/login.html")
    response.headers["Cache-Control"] = "no-store"
    return response


@router.post("/login")
@limiter.limit("5/15minutes")
async def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
) -> Response:
    client_ip = request.client.host if request.client else "unknown"
    db: Session = next(get_db())
    try:
        user = get_user_by_username(username, db)
        if not user or not verify_password(password, user.password_hash) or not user.is_active:
            db.add(LoginAttemptORM(
                ip_address=client_ip,
                username=username,
            ))
            db.commit()
            log.warning("login_failed", extra={"context": {"username": username}})
            return templates.TemplateResponse(
                request,
                "auth/login.html",
                {"error": "Неверное имя пользователя или пароль"},
                status_code=401,
            )

        session = create_session(user.id, client_ip, db)
        response = RedirectResponse("/tenders", status_code=302)
        response.set_cookie(
            "session_id",
            str(session.session_id),
            httponly=True,
            secure=True,
            samesite="lax",
            max_age=8 * 3600,
        )
        log.info("login_success", extra={"context": {"username": username}})
        return response
    finally:
        db.close()


@router.post("/logout")
async def logout(request: Request) -> Response:
    try:
        require_user(request)
    except _LoginRedirect:
        pass

    session_id_str = request.cookies.get("session_id")
    if session_id_str:
        from uuid import UUID
        db: Session = next(get_db())
        try:
            from web.auth import delete_session
            delete_session(UUID(session_id_str), db)
        except Exception as exc:
            log.warning(
                "logout_session_delete_failed",
                extra={"context": {"error_type": type(exc).__name__}},
            )
        finally:
            db.close()

    response = RedirectResponse("/login", status_code=302)
    response.delete_cookie("session_id")
    return response
