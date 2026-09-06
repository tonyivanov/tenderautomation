# NFR Design Patterns — Unit 3: Web Application

## Security Patterns

### 1. Security Headers Middleware (SECURITY-04)

**Паттерн**: Cross-Cutting Concern via Middleware

Один middleware перехватывает все HTML-ответы и добавляет заголовки — без дублирования в каждом роутере:

```python
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        ct = response.headers.get("content-type", "")
        if "text/html" in ct:
            response.headers.update({
                "Content-Security-Policy":
                    "default-src 'self'; "
                    "style-src 'self' cdn.jsdelivr.net; "
                    "script-src 'self' cdn.jsdelivr.net",
                "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
                "X-Content-Type-Options": "nosniff",
                "X-Frame-Options": "DENY",
                "Referrer-Policy": "strict-origin-when-cross-origin",
            })
        return response
```

---

### 2. Session Dependency — Deny by Default (SECURITY-08)

**Паттерн**: FastAPI Dependency Injection + Guard Clause

Все защищённые роутеры получают `current_user` через dependency. Если сессия невалидна — redirect до входа в бизнес-логику:

```python
async def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    session_id = request.cookies.get("session_id")
    if not session_id:
        raise RedirectException("/login")
    
    session = db.query(UserSession).filter(
        UserSession.session_id == session_id,
        UserSession.expires_at > datetime.now(timezone.utc)
    ).join(User).first()
    
    if not session:
        # Lazy cleanup of expired session cookie
        raise RedirectException("/login", clear_cookie=True)
    
    return session.user
```

Никакой бизнес-логики не выполняется для неаутентифицированных запросов.

---

### 3. Rate Limiting via slowapi (SECURITY-12)

**Паттерн**: Decorator-based Rate Limiting

```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@router.post("/login")
@limiter.limit("5/15minutes")   # 5 попыток с одного IP за 15 минут
async def login(request: Request, form: OAuth2PasswordRequestForm = Depends()):
    ...
```

При превышении → `429 Too Many Requests` (стандартный slowapi handler).

**Двойная защита**: slowapi (быстрый in-memory) + таблица `login_attempts` (аудит, более медленный DB-путь для анализа).

---

### 4. Global Error Handler — Fail Closed (SECURITY-15)

**Паттерн**: Top-Level Exception Catcher

```python
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    log.error("unhandled_exception",
              extra={"context": {"path": str(request.url), "error": type(exc).__name__}})
    # Не передаём детали пользователю (SECURITY-09)
    return templates.TemplateResponse(
        "errors/500.html",
        {"request": request},
        status_code=500,
    )

@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    return templates.TemplateResponse("errors/404.html", {"request": request}, status_code=404)
```

---

### 5. SRI for CDN Resources (SECURITY-13)

**Паттерн**: Subresource Integrity

Bootstrap 5 загружается из CDN только с проверенным integrity hash:

```html
<link rel="stylesheet"
  href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css"
  integrity="sha384-QWTKZyjpPEjISv5WaRU9OFeRpok6YctnYmDr5pNlyT2bRjXh0JMhjY6hW+ALEwIH"
  crossorigin="anonymous">
```

Если CDN ответит изменённым файлом — браузер заблокирует загрузку.

---

### 6. Input Validation Gateway (SECURITY-05)

**Паттерн**: Validation at Entry Point

Все POST-запросы валидируются Pydantic-моделями до любой бизнес-логики:

```python
class ActionForm(BaseModel):
    action: Literal["taken", "rejected", "deferred"]
    notes: str | None = Field(None, max_length=500)

class AnalysisForm(BaseModel):
    ai_tier: Literal["⭐", "🟡", "🟠", "🔴"]
    ai_rationale: str = Field(..., min_length=1, max_length=2000)
    ai_tool: str | None = Field(None, max_length=100)
```

FastAPI автоматически возвращает 422 при нарушении.

---

## Resilience Patterns

### 7. PRG — Post-Redirect-Get

**Паттерн**: Browser History Safety

Все POST-действия завершаются redirect:

```
POST /tenders/{id}/action → 303 See Other → GET /tenders
POST /tenders/{id}/analysis → 303 See Other → GET /tenders/{id}
POST /login (успех) → 302 → GET /tenders
POST /login (ошибка) → 200 (перерендер формы с ошибкой)
POST /logout → 302 → GET /login
```

Нет проблемы «двойной отправки» при F5 в браузере.

---

### 8. ZIP Export — In-Memory Streaming

**Паттерн**: Streaming Response без temp-файлов

```python
from io import BytesIO
import zipfile

def build_zip(jsonl: str, agents_md: str, date_str: str) -> BytesIO:
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(f"tenders_{date_str}.jsonl", jsonl)
        zf.writestr("AGENTS.md", agents_md)
    buf.seek(0)
    return buf
```

`StreamingResponse(buf, media_type="application/zip")` — не сохраняет на диск.

---

### 9. No-Cache for Login Page (SECURITY-09)

```python
@router.get("/login")
async def login_page(request: Request, response: Response):
    response.headers["Cache-Control"] = "no-store"
    return templates.TemplateResponse("auth/login.html", {"request": request})
```
