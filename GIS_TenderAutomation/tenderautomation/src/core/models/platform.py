from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class PlatformDescriptor(BaseModel):
    platform_id: str
    display_name: str
    base_url: str
    auth_method: str  # "credentials" | "playwright_session"
    rate_limit_sec: float = 1.0
    max_results_per_query: int = 1000
    field_mappings: dict[str, str] = Field(default_factory=dict)
    extra: dict[str, Any] = Field(default_factory=dict)


class PlatformCredentials(BaseModel):
    model_config = ConfigDict(json_schema_extra={"writeOnly": True})

    platform: str
    username: str
    password: str
    extra: dict[str, Any] = Field(default_factory=dict)

class AuthSession(BaseModel):
    platform: str
    token: str | None = None
    cookies: dict[str, str] = Field(default_factory=dict)
    expires_at: datetime | None = None

    def is_valid(self) -> bool:
        if self.expires_at is None:
            return bool(self.token or self.cookies)
        from datetime import timezone
        return datetime.now(timezone.utc) < self.expires_at
