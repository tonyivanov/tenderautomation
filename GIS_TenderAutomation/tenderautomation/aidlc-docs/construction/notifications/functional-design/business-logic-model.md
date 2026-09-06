# Business Logic Model — Unit 4: Notification Service

## 1. Telegram Alert (TelegramNotifier.send_alert)

**Вызывается**: EventBus.publish('tenders_qualified', count=N, platform_summary={...})

```
def send_alert(count: int, platform_summary: dict[str, int]) -> None:
    if not config.telegram_chat_ids:
        log.info("telegram_skipped_no_recipients")
        return

    text = (
        f"🔔 Новых тендеров: {count}\n"
        f"Открыть: {config.web_base_url}/tenders"
    )
    # Telegram limit: 4096 chars — truncate if somehow exceeded
    text = text[:4096]

    bot = telegram.Bot(token=config.telegram_bot_token)
    for chat_id in config.telegram_chat_ids:
        try:
            bot.send_message(chat_id=chat_id, text=text)
            log.info("telegram_sent", context={"chat_id": chat_id})
        except Exception as e:
            log.error("telegram_send_failed", context={"chat_id": chat_id, "error": str(e)})
            # Continue to next recipient — one failure doesn't block others
```

---

## 2. Email Digest (EmailDigest)

**Вызывается**: отдельным cron job раз в сутки
`python -m notifications.cli send-digest`

```
def build_digest(tenders: list[TenderModel], date_str: str) -> EmailDigestMessage:
    subject = f"TenderAutomation — новые тендеры за {date_str} ({len(tenders)} шт.)"

    lines = [f"TenderAutomation — новые тендеры за {date_str}", ""]
    for i, tender in enumerate(tenders, 1):
        budget_str = f"{tender.budget:,.0f} руб." if tender.budget else "не указана"
        deadline_str = tender.deadline.strftime('%d.%m.%Y') if tender.deadline else "—"
        lines += [
            f"{i}. [{tender.platform.upper()}] {tender.title}",
            f"   Заказчик: {tender.buyer or '—'} | НМЦК: {budget_str} | Дедлайн: {deadline_str}",
            f"   {tender.url}",
            "",
        ]

    if not tenders:
        lines.append("Новых квалифицированных тендеров нет.")

    return EmailDigestMessage(
        subject=subject,
        body_text="\n".join(lines),
        recipients=config.email_recipients,
    )


def send(message: EmailDigestMessage) -> None:
    if not message.recipients:
        log.info("email_skipped_no_recipients")
        return

    import smtplib
    from email.mime.text import MIMEText

    msg = MIMEText(message.body_text, "plain", "utf-8")
    msg["Subject"] = message.subject
    msg["From"] = config.smtp_from
    msg["To"] = ", ".join(message.recipients)

    try:
        with smtplib.SMTP(config.smtp_host, config.smtp_port) as server:
            server.ehlo()
            server.starttls()
            server.login(config.smtp_username, config.smtp_password)
            server.sendmail(config.smtp_from, message.recipients, msg.as_string())
        log.info("email_digest_sent", context={"recipients": len(message.recipients)})
    except Exception as e:
        log.error("email_send_failed", context={"error": str(e)})
        # Log and move on — cron will retry tomorrow
```

---

## 3. NotificationHandler (EventBus subscriber)

```
class NotificationHandler:
    def __init__(self, notifier: TelegramNotifier) -> None:
        self._notifier = notifier

    def on_tenders_qualified(self, count: int, platform_summary: dict) -> None:
        self._notifier.send_alert(count, platform_summary)

    def register(self, event_bus: EventBus) -> None:
        event_bus.subscribe("tenders_qualified", self.on_tenders_qualified)
```

---

## 4. CLI: send-digest

```
python -m notifications.cli send-digest

def send_digest():
    since = datetime.now(timezone.utc) - timedelta(hours=config.digest_hours)
    tenders = TenderRepository().get_qualified(since=since)
    date_str = datetime.now(timezone.utc).strftime('%d.%m.%Y')
    message = EmailDigest(config).build_digest(tenders, date_str)
    EmailDigest(config).send(message)
```
