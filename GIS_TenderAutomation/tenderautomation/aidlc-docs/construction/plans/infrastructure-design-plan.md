# Infrastructure Design Plan — Shared (All Units)

## Статус выполнения

- [x] Шаг 1: Ответы получены и проанализированы
- [x] Шаг 2: infrastructure-design.md — схема развёртывания
- [x] Шаг 3: deployment-architecture.md — конфигурации сервисов

---

## Уже зафиксировано (вопросов не требует)

| Компонент | Решение |
|---|---|
| Сервер | Linux VPS (Q6:C, requirements.md) |
| Планировщик | System cron |
| Web-сервер | Nginx → gunicorn + uvicorn (Unit 3 NFR) |
| БД | PostgreSQL (Application Design Q6:C) |
| Логи | JSONL-файлы в `data/` |
| Python-процессы | 2 отдельных: pipeline (cron) + web (gunicorn) |

---

## Уточняющие вопросы

### Q1: SSL/HTTPS
Как обеспечить HTTPS на VPS?

A) Let's Encrypt (certbot) — бесплатный, автообновление, стандарт
B) Купленный/корпоративный SSL-сертификат — ручная установка
C) Пока без HTTPS (только внутренняя сеть / VPN)
X) Другое (опишите после [Answer]:)

[Answer]: A

---

### Q2: PostgreSQL — где запускать?
A) Локально на том же VPS — проще, меньше стоимость
B) Отдельный managed PostgreSQL (Supabase, Neon, Railway, RDS) — managed backups, HA
C) Отдельный VPS/сервер только под БД
X) Другое (опишите после [Answer]:)

[Answer]: X в контейнере на том же сервере

---

### Q3: Бэкап PostgreSQL
Как делать резервные копии БД?

A) `pg_dump` по cron (ежесуточно) → локальный файл или S3/объектное хранилище
B) Встроенные механизмы managed-БД (если Q2:B или C)
C) Пока без бэкапа — данные некритичны для MVP
X) Другое (опишите после [Answer]:)

[Answer]: A
