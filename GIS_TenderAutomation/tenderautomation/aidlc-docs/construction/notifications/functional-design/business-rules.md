# Business Rules — Unit 4: Notification Service

**BR-N01**: Все параметры (токен, chat_ids, SMTP) — только из `.env`. Никаких хардкодированных значений.

**BR-N02**: Пустой `TELEGRAM_CHAT_IDS` → Telegram-уведомления пропускаются молча (log INFO). Не ошибка.

**BR-N03**: Пустой `EMAIL_RECIPIENTS` → email-дайджест пропускается молча (log INFO). Не ошибка.

**BR-N04**: Ошибка отправки в Telegram для одного chat_id → залогировать ERROR, перейти к следующему. Не прерывать цикл и не поднимать исключение в EventBus.

**BR-N05**: Ошибка SMTP → залогировать ERROR и завершить. Cron-задание завершится с ненулевым кодом — systemd/cron зафиксирует сбой.

**BR-N06**: Период дайджеста — последние `DIGEST_HOURS` часов (по умолчанию 24). Тендеры фильтруются по `collected_at >= now() - DIGEST_HOURS`.

**BR-N07**: Telegram-сообщение не превышает 4096 символов (лимит API). Если превышает — усечь с `…`.

**BR-N08**: Email-дайджест — plain-text (Q3:A). Без HTML. Кодировка UTF-8.

**BR-N09**: SMTP-пароль не логируется (SECURITY-03). В логах только host, port, recipients count.

**BR-N10**: `WEB_BASE_URL` из `.env` используется для ссылки `/tenders` в Telegram. Если не задан — ссылка не включается в сообщение.

**BR-N11**: Notification Service не имеет собственной БД-таблицы. Все данные берутся из Unit 1 (TenderRepository) и конфига.

---

## PBT-01: Compliance Summary

| Компонент | Свойство | Категория | Статус |
|---|---|---|---|
| `format_telegram_alert(N)` | Длина ≤ 4096 для любого N ≥ 0 | Invariant | Идентифицировано |
| `build_email_body(tenders)` | Каждый tender.url присутствует в body | Invariant | Идентифицировано |
| `parse_recipients(env_str)` | Нет пустых строк в результирующем list | Invariant | Идентифицировано |
