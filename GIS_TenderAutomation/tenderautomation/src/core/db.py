from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from core.config import settings

engine = create_engine(
    settings.database_url,
    pool_size=5,
    max_overflow=2,
    pool_timeout=30,
    pool_pre_ping=True,
    # sslmode controlled via DATABASE_URL (?sslmode=require for prod, ?sslmode=disable for local)
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


class Base(DeclarativeBase):
    pass
