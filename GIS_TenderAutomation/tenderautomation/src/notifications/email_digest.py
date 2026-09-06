from __future__ import annotations

import smtplib
from dataclasses import dataclass
from datetime import datetime, timezone
from email.mime.text import MIMEText

from core.logging import get_logger
from core.models import TenderModel

log = get_logger(__name__)


@dataclass
class EmailDigestMessage:
    subject: str
    body_text: str
    recipients: list[str]


class EmailDigest:
    def __init__(
        self,
        smtp_host: str,
        smtp_port: int,
        smtp_username: str,
        smtp_password: str,
        smtp_from: str,
        recipients: list[str],
    ) -> None:
        self._host = smtp_host
        self._port = smtp_port
        self._username = smtp_username
        self._password = smtp_password
        self._from = smtp_from
        self._recipients = [r.strip() for r in recipients if r.strip()]

    def build_digest(
        self, tenders: list[TenderModel], date_str: str | None = None
    ) -> EmailDigestMessage:
        if date_str is None:
            date_str = datetime.now(timezone.utc).strftime("%d.%m.%Y")

        subject = f"TenderAutomation — новые тендеры за {date_str} ({len(tenders)} шт.)"

        lines = [f"TenderAutomation — новые тендеры за {date_str}", ""]
        if not tenders:
            lines.append("Новых квалифицированных тендеров нет.")
        else:
            for i, t in enumerate(tenders, 1):
                budget = f"{t.budget:,.0f} руб." if t.budget else "не указана"
                deadline = t.deadline.strftime("%d.%m.%Y") if t.deadline else "—"
                lines += [
                    f"{i}. [{t.platform.upper()}] {t.title}",
                    f"   Заказчик: {t.buyer or '—'} | НМЦК: {budget} | Дедлайн: {deadline}",
                    f"   {t.url}",
                    "",
                ]

        return EmailDigestMessage(
            subject=subject,
            body_text="\n".join(lines),
            recipients=self._recipients,
        )

    def send(self, message: EmailDigestMessage) -> None:
        if not message.recipients:
            log.info("email_skipped_no_recipients")
            return

        msg = MIMEText(message.body_text, "plain", "utf-8")
        msg["Subject"] = message.subject
        msg["From"] = self._from
        msg["To"] = ", ".join(message.recipients)

        try:
            with smtplib.SMTP(self._host, self._port) as server:
                server.ehlo()
                server.starttls()
                server.login(self._username, self._password)
                server.sendmail(self._from, message.recipients, msg.as_string())
            log.info("email_digest_sent", extra={
                "context": {"recipients": len(message.recipients)}
            })
        except Exception as e:
            log.error("email_send_failed", extra={
                "context": {"host": self._host, "port": self._port, "error": type(e).__name__}
            })
            raise
