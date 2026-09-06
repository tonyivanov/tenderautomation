# NFR Design — Unit 4: Notification Service

## Паттерны

### 1. Fire-and-Forget (EventBus isolation)
Ошибки в `NotificationHandler` не поднимаются в `PipelineOrchestrator` — `EventBus.publish` перехватывает исключения per-handler (уже реализовано в `core.events.bus`).

### 2. Empty-Check Guard
```python
if not config.telegram_chat_ids:
    return  # silent skip, not an error
```
Применяется и для Telegram, и для email перед любыми внешними вызовами.

### 3. SMTP Context Manager (SECURITY-15)
```python
with smtplib.SMTP(host, port) as server:
    server.starttls()
    server.login(username, password)
    server.sendmail(...)
# Соединение закрывается автоматически
```

### 4. Sensitive Key Masking (SECURITY-03)
Логирование через `core.logging.JsonFormatter` — токен/пароль не в `context`, только `host`, `port`, `count`.

## Logical Components

```
src/notifications/
├── __init__.py
├── handler.py      # NotificationHandler — EventBus subscriber
├── telegram.py     # TelegramNotifier
├── email_digest.py # EmailDigest — build + send
└── cli.py          # send-digest CLI command
```
