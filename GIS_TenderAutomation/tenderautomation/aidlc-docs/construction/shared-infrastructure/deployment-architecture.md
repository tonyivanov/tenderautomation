# Deployment Architecture — TenderAutomation

## docker-compose.yml (Local macOS)

```yaml
# docker-compose.yml  ← корень проекта
version: "3.9"

services:
  postgres:
    image: postgres:16-alpine
    restart: unless-stopped
    environment:
      POSTGRES_USER: tender_user
      POSTGRES_PASSWORD: dev_password
      POSTGRES_DB: tender_db
    ports:
      - "127.0.0.1:5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data

volumes:
  pgdata:
```

**`.env` для локального запуска:**
```
DATABASE_URL=postgresql://tender_user:dev_password@localhost:5432/tender_db
B2BCENTER_USERNAME=...
# Bidzaar collection needs no credentials. Run scripts/bidzaar_login.py only
# when private-file deep analysis is required.
# Остальное — опционально для local dev
```

**Запуск (macOS):**
```bash
docker compose up -d          # Запустить PostgreSQL
PYTHONPATH=src alembic upgrade head  # Применить миграции

# Web-сервер с hot-reload
PYTHONPATH=src uvicorn web.app:app --reload --port 8000

# Создать первого пользователя
PYTHONPATH=src python -m web.cli add-user --username admin@gis.ru --role admin

# Pipeline вручную
PYTHONPATH=src python -m core.cli run-pipeline
```

---

## systemd: tender-web.service (Production)

```ini
# /etc/systemd/system/tender-web.service
[Unit]
Description=TenderAutomation Web Application
After=network.target docker.service
Requires=docker.service

[Service]
User=tender
WorkingDirectory=/opt/tender
EnvironmentFile=/opt/tender/.env
ExecStart=/opt/tender/venv/bin/gunicorn \
    -k uvicorn.workers.UvicornWorker \
    -w 2 \
    -b 127.0.0.1:8000 \
    --access-logfile - \
    --error-logfile - \
    web.app:app
Restart=always
RestartSec=5
Environment=PYTHONPATH=/opt/tender/src

[Install]
WantedBy=multi-user.target
```

```bash
systemctl enable tender-web
systemctl start tender-web
```

---

## Nginx: /etc/nginx/sites-available/tender

```nginx
server {
    listen 80;
    server_name your-domain.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    server_name your-domain.com;

    ssl_certificate     /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;
    ssl_protocols       TLSv1.2 TLSv1.3;

    # Static files — served by Nginx, not FastAPI
    location /static/ {
        alias /opt/tender/src/web/static/;
        expires 7d;
        add_header Cache-Control "public";
    }

    # FastAPI application
    location / {
        proxy_pass         http://127.0.0.1:8000;
        proxy_set_header   Host $host;
        proxy_set_header   X-Real-IP $remote_addr;
        proxy_set_header   X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
        proxy_read_timeout 30s;
    }
}
```

```bash
ln -s /etc/nginx/sites-available/tender /etc/nginx/sites-enabled/
certbot --nginx -d your-domain.com
nginx -t && systemctl reload nginx
```

---

## Cron: /etc/cron.d/tender

```cron
# TenderAutomation scheduled tasks
# Pipeline: every 6 hours
0 */6 * * * tender cd /opt/tender && PYTHONPATH=src /opt/tender/venv/bin/python -m core.cli run-pipeline >> /var/log/tender-pipeline.log 2>&1

# Email digest: daily at 07:00
0 7 * * * tender cd /opt/tender && PYTHONPATH=src /opt/tender/venv/bin/python -m notifications.cli send-digest >> /var/log/tender-digest.log 2>&1

# DB backup: daily at 02:00
0 2 * * * root /opt/tender/scripts/backup_db.sh >> /var/log/tender-backup.log 2>&1
```

---

## Скрипт деплоя (первичная установка)

```bash
#!/bin/bash
# deploy.sh — запускать на VPS от root

# 1. Docker для PostgreSQL
docker run -d \
  --name tender-postgres \
  --restart unless-stopped \
  -e POSTGRES_USER=tender_user \
  -e POSTGRES_PASSWORD="$(grep DATABASE_URL /opt/tender/.env | cut -d: -f3 | cut -d@ -f1)" \
  -e POSTGRES_DB=tender_db \
  -p 127.0.0.1:5432:5432 \
  -v tender-pgdata:/var/lib/postgresql/data \
  postgres:16-alpine

# 2. Python venv
cd /opt/tender
python3 -m venv venv
venv/bin/pip install -r requirements.txt
playwright install chromium  # для Bidzaar auth

# 3. Миграции
PYTHONPATH=src venv/bin/alembic upgrade head

# 4. Первый пользователь
PYTHONPATH=src venv/bin/python -m web.cli add-user \
  --username admin@gis.ru --role admin

# 5. Системные сервисы
cp deploy/tender-web.service /etc/systemd/system/
systemctl daemon-reload && systemctl enable tender-web && systemctl start tender-web

# 6. Nginx + SSL
apt install nginx certbot python3-certbot-nginx -y
cp deploy/nginx-tender.conf /etc/nginx/sites-available/tender
ln -s /etc/nginx/sites-available/tender /etc/nginx/sites-enabled/
certbot --nginx -d your-domain.com
systemctl reload nginx

# 7. Cron
cp deploy/tender.cron /etc/cron.d/tender
chmod 644 /etc/cron.d/tender
```

---

## Сравнение окружений

| | Local (macOS) | Production (Linux VPS) |
|---|---|---|
| PostgreSQL | Docker Compose | Docker container |
| Web server | uvicorn --reload | gunicorn + uvicorn workers |
| Reverse proxy | нет | Nginx + Let's Encrypt |
| Pipeline | ручной запуск | cron every 6h |
| Email digest | ручной запуск | cron daily 07:00 |
| Playwright auth | ручной (первый раз) | автоматический (.env) |
| `.env` | `dev_password`, нет Telegram | prod токены/пароли |
