# Logical Components — Unit 3: Web Application

## Структура пакетов

```
src/web/
├── app.py                  # FastAPI app factory + middleware registration
├── auth.py                 # Session dependency, bcrypt helpers
├── cli.py                  # Click CLI: add-user
├── deps.py                 # FastAPI dependencies (get_db, get_current_user)
├── middleware.py            # SecurityHeadersMiddleware
├── services/
│   └── export.py           # ExportService (ZIP + AGENTS.md)
├── routers/
│   ├── auth_router.py      # GET/POST /login, POST /logout
│   ├── tenders_router.py   # GET /tenders, GET /tenders/{id}
│   ├── actions_router.py   # POST /tenders/{id}/action, /analysis
│   ├── export_router.py    # GET /export/zip
│   └── history_router.py   # GET /history
├── templates/
│   ├── base.html
│   ├── auth/login.html
│   ├── tenders/list.html
│   ├── tenders/detail.html
│   ├── history/list.html
│   └── errors/404.html, 500.html
└── static/
    └── custom.css          # Минимальные кастомные стили поверх Bootstrap
```

---

## Компоненты

### `FastAPIApp` (`app.py`)

**Ответственность**: Инициализация приложения. Регистрация middleware, роутеров, обработчиков ошибок, slowapi.

```python
def create_app() -> FastAPI:
    app = FastAPI(docs_url=None, redoc_url=None)  # отключаем OpenAPI в prod (SECURITY-09)
    app.add_middleware(SecurityHeadersMiddleware)
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_exception_handler(Exception, global_exception_handler)
    app.mount("/static", StaticFiles(directory="src/web/static"), name="static")
    templates = Jinja2Templates(directory="src/web/templates")
    
    app.include_router(auth_router)
    app.include_router(tenders_router)
    app.include_router(actions_router)
    app.include_router(export_router)
    app.include_router(history_router)
    return app
```

---

### `SessionAuth` (`auth.py`)

**Ответственность**: bcrypt helpers, сессии.

```python
def hash_password(password: str) -> str: ...       # bcrypt, cost=12
def verify_password(plain: str, hashed: str) -> bool: ...
def create_session(user_id: UUID, ip: str, db: Session) -> UserSession: ...
def delete_session(session_id: UUID, db: Session) -> None: ...
```

---

### `SessionDependency` (`deps.py`)

**Ответственность**: FastAPI dependency для protected routes.

```python
def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    """Raises RedirectException if not authenticated."""
```

```python
def get_db() -> Generator[Session, None, None]:
    """Yields DB session, always closes."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

---

### `AuthRouter` (`routers/auth_router.py`)

| Endpoint | Method | Description |
|---|---|---|
| `/login` | GET | Форма входа (no-cache) |
| `/login` | POST | Validate creds → create session → redirect /tenders |
| `/logout` | POST | Delete session → redirect /login |

Rate limit на POST /login: `@limiter.limit("5/15minutes")`

---

### `TendersRouter` (`routers/tenders_router.py`)

| Endpoint | Method | Description |
|---|---|---|
| `/tenders` | GET | Список (pagination, filters) + is_new_map |
| `/tenders/{id}` | GET | Карточка + mark viewed + latest AI analysis |

---

### `ActionsRouter` (`routers/actions_router.py`)

| Endpoint | Method | Description |
|---|---|---|
| `/tenders/{id}/action` | POST | taken/rejected/deferred → DB + JSONL → redirect /tenders |
| `/tenders/{id}/analysis` | POST | AI analysis upload → DB → redirect /tenders/{id} |

---

### `ExportRouter` + `ExportService`

| Endpoint | Method | Description |
|---|---|---|
| `/export/zip` | GET | ZIP: tenders.jsonl + AGENTS.md |
| `/export/zip?ids=1,2` | GET | ZIP: only specified tenders |

`ExportService.build_export_bundle()`:
1. Fetch qualified tenders from `TenderRepository`
2. Build JSONL string
3. Read `AGENTS.md` base, inject `semantic_profile` from `filters/config.yaml`
4. Return `BytesIO` ZIP

---

### `HistoryRouter` (`routers/history_router.py`)

| Endpoint | Method | Description |
|---|---|---|
| `/history` | GET | История с фильтрами, 50 per page |

---

### `SecurityHeadersMiddleware` (`middleware.py`)

Применяет 5 security headers ко всем HTML-ответам (паттерн #1 выше).

---

### `WebCLI` (`cli.py`)

```python
@click.group()
def main(): pass

@main.command("add-user")
@click.option("--username", required=True)
@click.option("--password", required=True)
@click.option("--role", default="analyst", type=click.Choice(["analyst","manager","admin"]))
def add_user(username, password, role):
    """Create a new specialist user. Run from project root."""
```

---

## Взаимодействие компонентов

```
Browser
  │
  ├── GET /tenders
  │     → SecurityHeadersMiddleware
  │     → TendersRouter
  │         → SessionDependency.get_current_user() → User
  │         → TenderRepository.get_qualified() → list[TenderModel]
  │         → TenderViewRepo.get_is_new_map(user) → dict
  │         → Jinja2Templates.TemplateResponse("tenders/list.html")
  │
  ├── POST /tenders/{id}/action
  │     → ActionsRouter
  │         → SessionDependency → User
  │         → ActionForm (Pydantic validation → 422 if invalid)
  │         → TenderRepository.save_action()
  │         → ActionLogRepository.append()
  │         → RedirectResponse("/tenders", 303)
  │
  ├── GET /export/zip
  │     → ExportRouter
  │         → SessionDependency → User
  │         → ExportService.build_export_bundle()
  │             → TenderRepository.get_qualified()
  │             → read AGENTS.md + inject config.yaml profile
  │             → BytesIO ZIP
  │         → StreamingResponse(zip, "application/zip")
  │
  └── POST /login (rate-limited 5/15min per IP)
        → AuthRouter
            → verify_password() → bcrypt
            → create_session() → UUID cookie
            → RedirectResponse("/tenders", 302)
```
