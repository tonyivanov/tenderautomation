from __future__ import annotations

from core.logging import get_logger

log = get_logger(__name__)

_MAX_TG_LEN = 4096


class TelegramNotifier:
    def __init__(
        self,
        bot_token: str,
        chat_ids: list[str],
        web_base_url: str = "",
    ) -> None:
        self._token = bot_token
        self._chat_ids = [c.strip() for c in chat_ids if c.strip()]
        self._web_base_url = web_base_url.rstrip("/")

    def send_alert(self, count: int, platform_summary: dict[str, int]) -> None:
        if not self._chat_ids:
            log.info("telegram_skipped_no_recipients")
            return

        text = self._format_message(count)

        import telegram  # imported lazily — only when actually sending
        bot = telegram.Bot(token=self._token)

        for chat_id in self._chat_ids:
            try:
                import asyncio
                asyncio.run(bot.send_message(chat_id=chat_id, text=text))
                log.info("telegram_sent", extra={"context": {"chat_id": chat_id}})
            except Exception as e:
                log.error("telegram_send_failed", extra={
                    "context": {"chat_id": chat_id, "error": type(e).__name__}
                })

    def _format_message(self, count: int) -> str:
        parts = [f"🔔 Новых тендеров: {count}"]
        if self._web_base_url:
            parts.append(f"Открыть: {self._web_base_url}/tenders")
        text = "\n".join(parts)
        return text[:_MAX_TG_LEN]
