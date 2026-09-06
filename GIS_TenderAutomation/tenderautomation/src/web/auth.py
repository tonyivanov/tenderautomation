from __future__ import annotations

from datetime import datetime, timezone, timedelta
from uuid import UUID, uuid4

import bcrypt
from sqlalchemy.orm import Session

from core.config import settings
from core.orm.user import UserORM, UserSessionORM

SESSION_TTL_HOURS = 8
BCRYPT_ROUNDS = 12


def hash_password(password: str) -> str:
    return bcrypt.hashpw(
        password.encode("utf-8"), bcrypt.gensalt(rounds=BCRYPT_ROUNDS)
    ).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def create_session(user_id: UUID, ip: str | None, db: Session) -> UserSessionORM:
    session = UserSessionORM(
        session_id=uuid4(),
        user_id=user_id,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=SESSION_TTL_HOURS),
        ip_address=ip,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def delete_session(session_id: UUID, db: Session) -> None:
    db.query(UserSessionORM).filter(UserSessionORM.session_id == session_id).delete()
    db.commit()


def get_user_by_username(username: str, db: Session) -> UserORM | None:
    return db.query(UserORM).filter(UserORM.username == username).first()
