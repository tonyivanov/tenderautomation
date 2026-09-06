# Infrastructure Design — TenderAutomation (Shared)

## Окружения

| Окружение | Платформа | Назначение |
|---|---|---|
| **Production** | Linux VPS | Автоматический сбор, веб-интерфейс специалистов |
| **Local (dev/test)** | macOS (Docker Compose) | Разработка и ручное тестирование |

---

## Production (Linux VPS)

### Топология процессов

```
Internet
    │  HTTPS :443
    ▼
[Nginx]                      ← Reverse proxy, TLS termination, static files
    │  localhost:8000
    ▼
[gunicorn --workers 2]       ← WSGI/ASGI runner (uvicorn workers)
  └── FastAPI app             ← src/web/app.py
         │
         ├── [PostgreSQL]    ← Docker контейнер: postgres:16-alpine
         │   port 5432 (localhost only)
         │
         └── [data/]         ← JSONL-логи, Playwright state

[cron]  ─────────────────────► python -m core.cli run-pipeline
[cron]  ─────────────────────► python -m notifications.cli send-digest
```

### Сервисы

| Сервис | Как запускается | Пакет |
|---|---|---|
| PostgreSQL | Docker контейнер (`docker run`) | `postgres:16-alpine` |
| Web-приложение | systemd unit `tender-web.service` | gunicorn + uvicorn |
| Nginx | системный пакет `nginx` | nginx |
| Pipeline cron | `/etc/cron.d/tender` | python -m core.cli |
| Email digest cron | `/etc/cron.d/tender` | python -m notifications.cli |
| certbot | systemd timer / cron | certbot (Let's Encrypt) |

### Структура директорий на VPS

```
/opt/tender/               ← Корень приложения
├── .env                   ← Секреты (chmod 600)
├── src/                   ← Исходный код
├── venv/                  ← Python virtualenv
├── filters/               ← keywords.yaml, config.yaml
├── data/                  ← JSONL-логи, Playwright state (gitignored)
└── migrations/            ← Alembic migrations

/etc/nginx/sites-available/tender  ← Nginx конфиг
/etc/systemd/system/tender-web.service
/etc/cron.d/tender
```

---

## Local Development (macOS, Docker Compose)

### Топология

```
macOS terminal
    │
    ├── docker-compose up    ← PostgreSQL :5432
    │
    └── PYTHONPATH=src uvicorn web.app:app --reload --port 8000
                             ← FastAPI dev server (hot reload)
```

PostgreSQL в Docker Compose — единственный контейнер. Приложение запускается напрямую в virtualenv (не в Docker) для удобства отладки.

---

## SSL/HTTPS (Let's Encrypt)

```
certbot --nginx -d your-domain.com
# Auto-renewal через systemd timer (встроен в certbot)
```

---

## PostgreSQL в Docker

**Одинаковый образ** на prod и local:

```bash
# Production (docker run с автостартом)
docker run -d \
  --name tender-postgres \
  --restart unless-stopped \
  -e POSTGRES_USER=tender_user \
  -e POSTGRES_PASSWORD=<from .env> \
  -e POSTGRES_DB=tender_db \
  -p 127.0.0.1:5432:5432 \   # только localhost — не открыт наружу
  -v tender-pgdata:/var/lib/postgresql/data \
  postgres:16-alpine
```

`DATABASE_URL=postgresql://tender_user:password@localhost:5432/tender_db`

---

## Бэкап PostgreSQL

```bash
# /etc/cron.d/tender — ежесуточно в 02:00
0 2 * * * root /opt/tender/scripts/backup_db.sh

# backup_db.sh:
pg_dump -U tender_user tender_db | gzip > /opt/tender/backups/tender_$(date +%Y%m%d).sql.gz
find /opt/tender/backups -name "*.sql.gz" -mtime +30 -delete  # хранить 30 дней
```

---

## Мониторинг

- Логи pipeline: `journalctl -u tender-pipeline` / `/var/log/cron`
- Логи web: `journalctl -u tender-web`
- Таблица `collection_runs` в PostgreSQL — история сборов
- Отсутствие Telegram-уведомлений за сутки = сигнал проверить cron
