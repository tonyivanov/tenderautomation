# Domain Entities — Unit 4: Notification Service

## NotificationConfig (из Settings)

Параметры уведомлений загружаются из `.env` через `pydantic-settings`.

| Поле | Тип | Описание |
|---|---|---|
| `telegram_bot_token` | `str` | Токен Telegram Bot API |
| `telegram_chat_ids` | `list[str]` | Список chat_id через запятую (Q1:B) |
| `smtp_host` | `str` | SMTP-сервер (например `smtp.gmail.com`) |
| `smtp_port` | `int` | SMTP-порт (587 = TLS, 465 = SSL) |
| `smtp_username` | `str` | Логин SMTP |
| `smtp_password` | `str` | Пароль SMTP |
| `smtp_from` | `str` | Адрес отправителя |
| `email_recipients` | `list[str]` | Список email-получателей через запятую (Q4:B) |
| `web_base_url` | `str` | Базовый URL веб-интерфейса (для ссылок в уведомлениях) |
| `digest_hours` | `int` | Период дайджеста в часах (по умолчанию 24) |

---

## TelegramAlert (in-memory, не персистируется)

| Поле | Тип | Описание |
|---|---|---|
| `count` | `int` | Количество новых квалифицированных тендеров |
| `platform_summary` | `dict[str, int]` | `{"bidzaar": N, "b2bcenter": M}` |
| `web_url` | `str` | Ссылка на `/tenders` |

**Формат сообщения** (Q2:A — краткое):
```
🔔 Новых тендеров: {count}
Открыть: {web_url}/tenders
```

---

## EmailDigestMessage (in-memory, не персистируется)

| Поле | Тип | Описание |
|---|---|---|
| `subject` | `str` | Тема письма |
| `body_text` | `str` | Тело письма (plain-text, Q3:A — список тендеров) |
| `recipients` | `list[str]` | Получатели |

**Формат тела** (Q3:A):
```
TenderAutomation — новые тендеры за {date}

1. [B2B-Center] Разработка DevOps-инфраструктуры
   Заказчик: ООО Ромашка | НМЦК: 1 500 000 руб. | Дедлайн: 31.07.2026
   https://www.b2b-center.ru/market/12345/

2. [Bidzaar] Мониторинг инфраструктуры...
```

---

## PBT-01: Тестируемые свойства

| Свойство | Категория | Компонент |
|---|---|---|
| `format_telegram_alert(N)` → длина ≤ 4096 символов (лимит Telegram) | Invariant | TelegramNotifier |
| `build_email_body(tenders)` → каждый tender.id присутствует в теле | Invariant | EmailDigest |
| `parse_recipients(".env value")` → корректный list[str] без пустых | Invariant | Settings |
