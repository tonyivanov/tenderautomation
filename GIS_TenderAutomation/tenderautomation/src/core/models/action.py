from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


ActionType = Literal["taken", "rejected", "deferred", "ai_analysis"]
AiTier = Literal["⭐", "🟡", "🟠", "🔴"]


class TenderAction(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    tender_id: str
    action_type: ActionType
    user_id: str
    notes: str | None = None
    ai_tier: AiTier | None = None
    ai_rationale: str | None = None
    ai_tool: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def to_jsonl_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "tender_id": self.tender_id,
            "action_type": self.action_type,
            "user_id": self.user_id,
            "notes": self.notes,
            "ai_tier": self.ai_tier,
            "ai_rationale": self.ai_rationale,
            "ai_tool": self.ai_tool,
            "created_at": self.created_at.isoformat(),
        }


class AnalysisResult(BaseModel):
    ai_tier: AiTier
    ai_rationale: str
    ai_tool: str | None = None


class HistoryFilters(BaseModel):
    platform: str | None = None
    status: str | None = None
    user_id: str | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None
    search: str | None = None
    limit: int = 100
    offset: int = 0
