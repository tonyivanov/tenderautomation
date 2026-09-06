import pytest
from datetime import datetime, timezone
import asyncio

from core.adapters import AdapterRegistry
from core.adapters.base import PlatformAdapter
from core.models import AuthSession, ProcedureState


class _Adapter:
    def __init__(self, platform: str) -> None:
        self._platform = platform

    def platform_id(self) -> str:
        return self._platform


def test_registry_round_trip_and_platform_ids() -> None:
    registry = AdapterRegistry()
    adapter = _Adapter("example")
    registry.register(adapter)  # type: ignore[arg-type]
    assert registry.get("example") is adapter
    assert registry.get_all() == [adapter]
    assert registry.platform_ids() == ["example"]


def test_registry_rejects_unknown_platform() -> None:
    with pytest.raises(ValueError, match="No adapter registered"):
        AdapterRegistry().get("missing")


def test_default_inspection_contract_fails_closed(tender_factory) -> None:
    result = asyncio.run(
        PlatformAdapter.inspect_tender(
            object(),  # type: ignore[arg-type]
            AuthSession(platform="example", token="opaque"),
            tender_factory(),
            None,
        )
    )
    assert not result.verified
    assert result.state is ProcedureState.UNKNOWN
    assert result.attempted_at.tzinfo is not None
    assert "opaque" not in repr(result)
