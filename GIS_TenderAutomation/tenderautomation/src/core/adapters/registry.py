from __future__ import annotations

from core.adapters.base import PlatformAdapter


class AdapterRegistry:
    def __init__(self) -> None:
        self._adapters: dict[str, PlatformAdapter] = {}

    def register(self, adapter: PlatformAdapter) -> None:
        self._adapters[adapter.platform_id()] = adapter

    def get(self, platform_id: str) -> PlatformAdapter:
        try:
            return self._adapters[platform_id]
        except KeyError:
            raise ValueError(f"No adapter registered for platform: {platform_id}")

    def get_all(self) -> list[PlatformAdapter]:
        return list(self._adapters.values())

    def platform_ids(self) -> list[str]:
        return list(self._adapters.keys())
