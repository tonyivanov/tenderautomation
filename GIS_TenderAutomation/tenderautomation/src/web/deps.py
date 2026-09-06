from __future__ import annotations

from datetime import datetime, timezone
from typing import Generator
from uuid import UUID

from fastapi import Cookie, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from core.db import SessionLocal
from core.orm.user import UserORM, UserSessionORM


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class _NeedsLogin(Exception):
    def __init__(self, clear_cookie: bool = False):
        self.clear_cookie = clear_cookie


def get_current_user(request: Request, db: Session | None = None) -> UserORM:
    if db is None:
        db = next(get_db())

    session_id_str = request.cookies.get("session_id")
    if not session_id_str:
        raise _NeedsLogin()

    try:
        session_id = UUID(session_id_str)
    except ValueError:
        raise _NeedsLogin(clear_cookie=True)

    session = (
        db.query(UserSessionORM)
        .filter(
            UserSessionORM.session_id == session_id,
            UserSessionORM.expires_at > datetime.now(timezone.utc),
        )
        .join(UserORM)
        .first()
    )

    if not session:
        raise _NeedsLogin(clear_cookie=True)

    if not session.user.is_active:
        db.delete(session)
        db.commit()
        raise _NeedsLogin(clear_cookie=True)

    return session.user


def require_user(request: Request, db: Session | None = None) -> UserORM:
    try:
        return get_current_user(request, db)
    except _NeedsLogin as e:
        response = RedirectResponse("/login", status_code=302)
        if e.clear_cookie:
            response.delete_cookie("session_id")
        raise _LoginRedirect(response)


class _LoginRedirect(Exception):
    def __init__(self, response: RedirectResponse):
        self.response = response
