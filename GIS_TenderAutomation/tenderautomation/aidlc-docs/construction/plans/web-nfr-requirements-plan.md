# NFR Requirements Plan — Unit 3: Web Application

## Статус выполнения

- [x] Шаг 1: Ответы получены и проанализированы
- [x] Шаг 2: nfr-requirements.md
- [x] Шаг 3: tech-stack-decisions.md

---

## Уже зафиксировано (вопросы не нужны)

| Область | Решение |
|---|---|
| Web framework | FastAPI + Jinja2 SSR |
| Auth | Session-based (cookie), bcrypt пароли |
| DB | PostgreSQL (users, sessions, tender_views, login_attempts) |
| Security Baseline | SECURITY-01–15, все блокирующие |
| HTTP Security Headers | BR-W24 (CSP, HSTS, X-Frame-Options и др.) |
| Brute-force protection | 5 попыток / 15 мин / IP (BR-W05) |
| PRG pattern | POST → redirect, нет двойной отправки |
| PBT framework | Hypothesis |

---

## Уточняющие вопросы

### Q1: CSS-фреймворк для Jinja2-шаблонов
Какой подход к стилизации интерфейса?

A) Bootstrap 5 (CDN) — зрелый, много компонентов, не нужен сборщик
B) Tailwind CSS (CDN Play CDN) — utility-first, современный, без сборки
C) Чистый CSS — минимальные зависимости, пишем сами
X) Другое (опишите после [Answer]:)

[Answer]: A

---

### Q2: Rate limiting — где реализовать?
Brute-force защита (BR-W05) нужна. Как её реализовать?

A) В FastAPI middleware — in-app, без внешних зависимостей (используем таблицу `login_attempts`)
B) `slowapi` библиотека для FastAPI — декоратор `@limiter.limit("5/15minute")`
C) Nginx-уровень — `limit_req_zone` в конфиге nginx (без кода в приложении)
X) Другое (опишите после [Answer]:)

[Answer]: B
