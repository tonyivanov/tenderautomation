from __future__ import annotations

from collections import defaultdict
from typing import Callable

from core.logging import get_logger

log = get_logger(__name__)


class EventBus:
    def __init__(self) -> None:
        self._handlers: dict[str, list[Callable[..., None]]] = defaultdict(list)

    def subscribe(self, event: str, handler: Callable[..., None]) -> None:
        self._handlers[event].append(handler)

    def publish(self, event: str, **payload: object) -> None:
        for handler in self._handlers.get(event, []):
            try:
                handler(**payload)
            except Exception as e:
                log.error(
                    "event_handler_error",
                    extra={"context": {"event": event, "handler": handler.__name__, "error": str(e)}},
                )
