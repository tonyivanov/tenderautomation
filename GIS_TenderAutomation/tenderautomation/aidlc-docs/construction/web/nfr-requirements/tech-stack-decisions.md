# Tech Stack Decisions — Unit 3: Web Application

## Сводная таблица

| Слой | Библиотека | Версия | Обоснование |
|---|---|---|---|
| Web framework | FastAPI | ≥0.115.0 | Application Design Q1:A |
| Templates | Jinja2 | ≥3.1.4 | Встроен в FastAPI via `Jinja2Templates` |
| Static files | `starlette.staticfiles` | (FastAPI dep) | Встроен, Nginx отдаёт в prod |
| Password hashing | bcrypt | ≥4.2.0 | SECURITY-12: adaptive hash, cost=12 |
| Rate limiting | slowapi | ≥0.1.9 | Q2:B — декоратор `@limiter.limit()`, Starlette-совместим |
| CSS framework | Bootstrap 5 (CDN) | 5.3.x | Q1:A — CDN с SRI integrity hash |
| ASGI server | uvicorn | ≥0.30.0 | Dev. В prod: gunicorn + uvicorn workers |
| WSGI/ASGI prod | gunicorn | ≥23.0.0 | Production ASGI: `gunicorn -k uvicorn.workers.UvicornWorker` |
| ZIP export | `zipfile` (stdlib) | built-in | Нет доп. зависимостей |
| YAML loading | PyYAML | ≥6.0.2 | Уже в requirements.txt |

**Унаследовано из Unit 1**: SQLAlchemy, psycopg2-binary, Pydantic, pydantic-settings, python-dotenv, click, core.logging

## Детали ключевых решений

### Bootstrap 5 CDN с SRI (Q1:A + SECURITY-13)

```html
<!-- В base.html — CDN с integrity hash (SECURITY-13) -->
<link rel="stylesheet"
  href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css"
  integrity="sha384-QWTKZyjpPEjISv5WaRU9OFeRpok6YctnYmDr5pNlyT2bRjXh0JMhjY6hW+ALEwIH"
  crossorigin="anonymous">
<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"
  integrity="sha384-YvpcrYf0tY3lHB60NNkmXc4s9bIOgUxi8T/jzmig7Z7Bpn5RTnk0b3Cm01rN6s"
  crossorigin="anonymous"></script>
```

### slowapi — Rate Limiting (Q2:B)

```python
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)

# В app.py:
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# На POST /login:
@router.post("/login")
@limiter.limit("5/15minutes")
async def login(request: Request, ...): ...
```

**In-memory store** (default) — достаточно для одного Gunicorn-процесса.

### bcrypt (SECURITY-12)

```python
import bcrypt

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode()

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
```

### HTTP Security Headers Middleware (SECURITY-04)

```python
from starlette.middleware.base import BaseHTTPMiddleware

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        if "text/html" in response.headers.get("content-type", ""):
            response.headers["Content-Security-Policy"] = "default-src 'self'; style-src 'self' cdn.jsdelivr.net; script-src 'self' cdn.jsdelivr.net"
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["X-Frame-Options"] = "DENY"
            response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response
```

## Обновлённый requirements.txt (добавить)

```
fastapi==0.115.5
uvicorn==0.32.1
gunicorn==23.0.0
jinja2==3.1.4
bcrypt==4.2.0
slowapi==0.1.9
python-multipart==0.0.12
```

## Что NOT используется

| | Причина |
|---|---|
| JWT | Session-based выбран (Q3:A Application Design) |
| Redis | Single-process → in-memory slowapi достаточен |
| Tailwind | Bootstrap проще для SSR без сборщика (Q1:A) |
| Celery | Нет async задач в Web unit |
| itsdangerous | Нет signed cookies — используем UUID в PostgreSQL |
