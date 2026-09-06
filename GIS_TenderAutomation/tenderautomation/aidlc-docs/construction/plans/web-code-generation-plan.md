# Code Generation Plan — Unit 3: Web Application

## Контекст

**Application code**: `src/web/` (новые), `src/core/orm/user.py` (новый), `migrations/versions/0002_*`
**Tests**: `tests/unit/web/`
**Stories**: US-03, US-04, US-05, US-06, US-07
**Зависит от**: Unit 1 (TenderRepository, ActionLogRepository, SessionLocal, core.models)

---

## Статус выполнения

### Шаг 1: Зависимости и миграция
- [x] 1.1 Обновить `requirements.txt` — добавить fastapi, uvicorn, gunicorn, jinja2, bcrypt, slowapi, python-multipart
- [x] 1.2 `src/core/orm/user.py` — UserORM, UserSessionORM, TenderViewORM, LoginAttemptORM
- [x] 1.3 Обновить `src/core/orm/__init__.py`
- [x] 1.4 `migrations/versions/0002_web_schema.py` — users, sessions, tender_views, login_attempts

### Шаг 2: Основа приложения
- [x] 2.1 `src/web/__init__.py`
- [x] 2.2 `src/web/middleware.py` — SecurityHeadersMiddleware
- [x] 2.3 `src/web/auth.py` — hash_password, verify_password, create_session, delete_session
- [x] 2.4 `src/web/deps.py` — get_db, get_current_user (FastAPI dependency)
- [x] 2.5 `src/web/app.py` — create_app() factory

### Шаг 3: CLI
- [x] 3.1 `src/web/cli.py` — add-user command

### Шаг 4: Сервисы
- [x] 4.1 `src/web/services/__init__.py`
- [x] 4.2 `src/web/services/export.py` — ExportService (ZIP + AGENTS.md dynamic)

### Шаг 5: Роутеры
- [x] 5.1 `src/web/routers/__init__.py`
- [x] 5.2 `src/web/routers/auth_router.py` — /login GET+POST, /logout POST
- [x] 5.3 `src/web/routers/tenders_router.py` — /tenders GET, /tenders/{id} GET
- [x] 5.4 `src/web/routers/actions_router.py` — /tenders/{id}/action POST, /analysis POST
- [x] 5.5 `src/web/routers/export_router.py` — /export/zip GET
- [x] 5.6 `src/web/routers/history_router.py` — /history GET

### Шаг 6: AGENTS.md (статический базовый файл)
- [x] 6.1 `AGENTS.md` — LLM-agnostic инструкция с placeholder {{SEMANTIC_PROFILE}}

### Шаг 7: Jinja2-шаблоны
- [x] 7.1 `src/web/templates/base.html` — layout, nav, Bootstrap 5 SRI
- [x] 7.2 `src/web/templates/auth/login.html`
- [x] 7.3 `src/web/templates/tenders/list.html`
- [x] 7.4 `src/web/templates/tenders/detail.html`
- [x] 7.5 `src/web/templates/history/list.html`
- [x] 7.6 `src/web/templates/errors/404.html`, `500.html`
- [x] 7.7 `src/web/static/custom.css`

### Шаг 8: Тесты
- [x] 8.1 `tests/unit/web/__init__.py`
- [x] 8.2 `tests/unit/web/test_auth.py` — PBT: bcrypt round-trip, verify_password
- [x] 8.3 `tests/unit/web/test_export.py` — PBT: JSONL export round-trip

### Шаг 9: Документация
- [x] 9.1 `aidlc-docs/construction/web/code/code-summary.md`

---

## Трассировка историй

| История | Шаги |
|---|---|
| US-03 (скачивание JSONL+AGENTS.md) | 4.2, 5.5, 6.1 |
| US-04 (просмотр, индикатор новых) | 5.3, 7.3, 7.4 |
| US-05 (загрузка AI-анализа) | 5.4, 7.4 |
| US-06 (решения + лог) | 5.4, 7.4 |
| US-07 (история) | 5.6, 7.5 |
