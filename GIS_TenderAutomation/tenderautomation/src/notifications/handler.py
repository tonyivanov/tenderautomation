from __future__ import annotations

from core.events.bus import EventBus
from core.logging import get_logger
from notifications.telegram import TelegramNotifier

log = get_logger(__name__)


class NotificationHandler:
    def __init__(self, notifier: TelegramNotifier) -> None:
        self._notifier = notifier

    def register(self, event_bus: EventBus) -> None:
        event_bus.subscribe("tenders_qualified", self.on_tenders_qualified)

    def on_tenders_qualified(self, count: int, platform_summary: dict[str, int]) -> None:
        log.info("notifications_triggered", extra={"context": {"count": count}})
        self._notifier.send_alert(count, platform_summary)
