from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.db import Base


class TenderORM(Base):
    __tablename__ = "tenders"

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    platform: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    external_id: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    buyer: Mapped[str | None] = mapped_column(Text, nullable=True)
    budget: Mapped[float | None] = mapped_column(Numeric(18, 2), nullable=True)
    deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    raw_data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    prefilter_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    qualification_tier: Mapped[str | None] = mapped_column(String(20), nullable=True)
    matched_keywords: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", index=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    collected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        server_default=func.now(), onupdate=func.now()
    )
    procedure_state: Mapped[str] = mapped_column(
        String(20), nullable=False, default="unknown", server_default="unknown", index=True
    )
    procedure_checked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    procedure_last_attempt_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    procedure_source: Mapped[str | None] = mapped_column(String(50), nullable=True)
    procedure_error_category: Mapped[str | None] = mapped_column(String(50), nullable=True)

    actions: Mapped[list["TenderActionORM"]] = relationship(
        "TenderActionORM", back_populates="tender", lazy="select"
    )


class TenderActionORM(Base):
    __tablename__ = "tender_actions"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    tender_id: Mapped[str] = mapped_column(
        String(255), ForeignKey("tenders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    action_type: Mapped[str] = mapped_column(String(20), nullable=False)
    user_id: Mapped[str] = mapped_column(String(255), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_tier: Mapped[str | None] = mapped_column(String(10), nullable=True)
    ai_rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_tool: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    tender: Mapped["TenderORM"] = relationship("TenderORM", back_populates="actions")


class CollectionRunORM(Base):
    __tablename__ = "collection_runs"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    platform: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="running", index=True)
    new_tenders_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_tenders_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
