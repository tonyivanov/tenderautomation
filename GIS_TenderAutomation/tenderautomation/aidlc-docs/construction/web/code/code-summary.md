# Code Summary — Unit 3: Web Application

## Созданные файлы

### Core ORM additions
| Файл | Содержание |
|---|---|
| `src/core/orm/user.py` | UserORM, UserSessionORM, TenderViewORM, LoginAttemptORM |
| `migrations/versions/0002_web_schema.py` | Таблицы users, user_sessions, tender_views, login_attempts |

### Web Application (`src/web/`)
| Файл | Содержание |
|---|---|
| `app.py` | `create_app()` — FastAPI factory, middleware, slowapi, error handlers |
| `middleware.py` | `SecurityHeadersMiddleware` — 5 HTTP security headers |
| `auth.py` | `hash_password`, `verify_password` (bcrypt cost=12), `create_session`, `delete_session` |
| `deps.py` | `get_db`, `get_current_user`, `require_user` — FastAPI dependencies |
| `cli.py` | `add-user` CLI command |
| `services/export.py` | `ExportService` — ZIP с JSONL + AGENTS.md (dynamic profile) |
| `routers/auth_router.py` | GET/POST /login (slowapi rate limit), POST /logout |
| `routers/tenders_router.py` | GET /tenders (pagination, is_new), GET /tenders/{id} (mark viewed) |
| `routers/actions_router.py` | POST /tenders/{id}/action, POST /tenders/{id}/analysis |
| `routers/export_router.py` | GET /export/zip |
| `routers/history_router.py` | GET /history |

### Templates (`src/web/templates/`)
| Файл | Содержание |
|---|---|
| `base.html` | Bootstrap 5 CDN (SRI), navbar, unread badge |
| `auth/login.html` | Login form с error display |
| `tenders/list.html` | Таблица тендеров, фильтры, пагинация, new-indicator, export button |
| `tenders/detail.html` | Карточка, AI-анализ форма, кнопки решений, история действий |
| `history/list.html` | История с фильтрами и пагинацией |
| `errors/404.html`, `500.html` | Generic error pages (SECURITY-09) |

### Other
| Файл | Содержание |
|---|---|
| `AGENTS.md` | LLM-agnostic инструкция с `{{SEMANTIC_PROFILE}}` placeholder |
| `src/web/static/custom.css` | Минимальные Bootstrap overrides |

### Tests (`tests/unit/web/`)
| Файл | Покрытие |
|---|---|
| `test_auth.py` | PBT: bcrypt round-trip (verify own hash), wrong password fails |
| `test_export.py` | PBT: JSONL each line valid JSON, round-trip fields, empty list |

## Ключевые решения

- **PRG pattern**: все POST → 303 redirect (нет двойной отправки)
- **Deny by default**: `require_user()` dependency на всех protected routes
- **slowapi**: `@limiter.limit("5/15minutes")` на POST /login
- **AGENTS.md**: статический base + dynamic `{{SEMANTIC_PROFILE}}` из config.yaml
- **In-memory ZIP**: `StreamingResponse(BytesIO)`, нет temp-файлов

## Запуск (development)

```bash
# Установка
pip install -r requirements.txt

# Создать пользователя
PYTHONPATH=src python -m web.cli add-user --username admin@gis.ru --role admin

# Запуск dev-сервера
PYTHONPATH=src uvicorn web.app:app --reload --port 8000
```
