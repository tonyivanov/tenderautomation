# NFR Requirements — Unit 4: Notification Service

## Производительность

- Telegram-уведомление: < 5с на сообщение (API call, не критично)
- Email-дайджест: полный цикл (fetch + build + send) < 60с
- Не блокирует pipeline: вызывается через EventBus, ошибки изолированы

## Безопасность (Security Baseline)

| Правило | Применение |
|---|---|
| SECURITY-03 | SMTP-пароль, Telegram-токен — не логируются. В логах: host, port, recipient count |
| SECURITY-10 | `python-telegram-bot` — точная версия в requirements.txt |
| SECURITY-12 | Токены и пароли — только из `.env` / `Settings` |
| SECURITY-15 | Ошибки API/SMTP — log + continue, не raise; finally-блоки для SMTP-соединений |

**SECURITY N/A**: SECURITY-01–02, SECURITY-04–09, SECURITY-11, SECURITY-13–14 (нет HTTP, нет БД, нет десериализации внешних данных).

## Надёжность

- Telegram: ошибка одного chat_id → continue к следующему
- SMTP: ошибка → log ERROR, cron-задание завершается с кодом 1 (systemd фиксирует)
- Пустые получатели → молчаливый пропуск (не ошибка)

## Tech Stack

| | |
|---|---|
| Telegram | `python-telegram-bot>=21.0` |
| Email | `smtplib` (stdlib, не нужна доп. библиотека) |
| Логирование | `core.logging.get_logger()` (унаследовано) |
| CLI | `click` (уже в requirements.txt) |
| PBT | `hypothesis` (уже в requirements-dev.txt) |

**Добавить в requirements.txt**: `python-telegram-bot==21.6`
