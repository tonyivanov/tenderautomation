# Code Summary — Unit 4: Notification Service

## Созданные файлы

| Файл | Содержание |
|---|---|
| `src/notifications/__init__.py` | Реэкспорт NotificationHandler, TelegramNotifier, EmailDigest |
| `src/notifications/handler.py` | `NotificationHandler` — EventBus subscriber, `on_tenders_qualified` |
| `src/notifications/telegram.py` | `TelegramNotifier` — async send per chat_id, 4096 limit, empty-check guard |
| `src/notifications/email_digest.py` | `EmailDigest` — build plain-text digest + SMTP starttls send |
| `src/notifications/cli.py` | `send-digest` CLI command |
| `src/core/config.py` | Обновлён: +telegram/email настройки + helper methods |
| `src/core/cli.py` | Обновлён: NotificationHandler зарегистрирован в pipeline |
| `.env.example` | Обновлён: примеры Telegram и SMTP переменных |
| `tests/unit/notifications/test_notifications.py` | PBT: Telegram message len ≤ 4096; email body содержит все URLs; recipients parsing |

## Ключевые паттерны

- **Fire-and-forget**: ошибки handler'а изолированы в EventBus (не поднимаются в pipeline)
- **Empty-check guard**: пустые получатели → log INFO + return, не ошибка
- **SMTP context manager**: `with smtplib.SMTP(...) as server:` — соединение всегда закрывается
- **No secrets in logs**: host/port/count — да; token/password — нет

## Запуск

```bash
# Email дайджест (добавить в cron раз в сутки)
PYTHONPATH=src python -m notifications.cli send-digest

# Pipeline (Telegram уведомление срабатывает автоматически)
PYTHONPATH=src python -m core.cli run-pipeline
```
