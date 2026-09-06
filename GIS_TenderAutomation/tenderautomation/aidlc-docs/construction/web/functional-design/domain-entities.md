# Domain Entities — Unit 3: Web Application

## User

Учётная запись специалиста. Создаётся через CLI-команду `add-user`.

| Поле | Тип | Описание |
|---|---|---|
| `id` | `UUID` | PK |
| `username` | `str` | Уникальный логин (email или короткое имя) |
| `password_hash` | `str` | bcrypt hash пароля |
| `role` | `str` | `analyst` \| `manager` \| `admin` |
| `is_active` | `bool` | False = деактивирован (не может войти) |
| `created_at` | `datetime` | Момент создания |

---

## UserSession

Серверная сессия. Хранится в PostgreSQL, ID передаётся в cookie.

| Поле | Тип | Описание |
|---|---|---|
| `session_id` | `UUID` | PK, значение cookie |
| `user_id` | `UUID` | FK → User.id |
| `created_at` | `datetime` | Момент создания |
| `expires_at` | `datetime` | Время истечения (created_at + SESSION_TTL_HOURS) |
| `ip_address` | `str \| None` | IP для аудита |

Сессия **уничтожается** при logout. Истёкшие сессии — lazy cleanup при валидации.

---

## TenderView

Отметка просмотра тендера конкретным пользователем (per-user "new" tracking).

| Поле | Тип | Описание |
|---|---|---|
| `tender_id` | `str` | FK → tenders.id |
| `user_id` | `UUID` | FK → users.id |
| `viewed_at` | `datetime` | Момент первого просмотра |

Составной PK: `(tender_id, user_id)`. INSERT OR IGNORE — повторный просмотр не меняет запись.

---

## LoginAttempt

Счётчик неудачных попыток входа для защиты от brute-force.

| Поле | Тип | Описание |
|---|---|---|
| `ip_address` | `str` | IP-адрес клиента |
| `attempt_at` | `datetime` | Момент попытки |
| `username` | `str` | Введённый логин |

Используется только для rate-limiting: количество записей за последние 15 минут с одного IP.

---

## ExportBundle (in-memory, не персистируется)

Результат ExportService — передаётся как ZIP-ответ.

| Поле | Тип | Описание |
|---|---|---|
| `jsonl_content` | `str` | JSONL-строка (все квалифицированные тендеры) |
| `agents_md_content` | `str` | AGENTS.md с вставленным semantic_profile |
| `filename_prefix` | `str` | Например `tenders_2026-06-04` |

---

## Миграция (Alembic)

Добавить в `0002_web_schema.py`:
```sql
CREATE TABLE users (id UUID PK, username TEXT UNIQUE, password_hash TEXT, role TEXT, is_active BOOL, created_at TIMESTAMPTZ);
CREATE TABLE user_sessions (session_id UUID PK, user_id UUID FK, created_at TIMESTAMPTZ, expires_at TIMESTAMPTZ, ip_address TEXT);
CREATE TABLE tender_views (tender_id TEXT, user_id UUID, viewed_at TIMESTAMPTZ, PRIMARY KEY (tender_id, user_id));
CREATE TABLE login_attempts (ip_address TEXT, attempt_at TIMESTAMPTZ, username TEXT);
CREATE INDEX ix_user_sessions_user_id ON user_sessions (user_id);
CREATE INDEX ix_user_sessions_expires_at ON user_sessions (expires_at);
CREATE INDEX ix_login_attempts_ip_at ON login_attempts (ip_address, attempt_at);
```

---

## PBT-01: Тестируемые свойства (Unit 3)

| Свойство | Категория | Компонент |
|---|---|---|
| bcrypt round-trip: `verify(hash(pw), pw) == True` | Round-trip | Auth |
| JSONL export → parse → те же поля | Round-trip | ExportService |
| Session ID всегда уникален (UUID4) | Invariant | SessionService |
| Tender "is_new" = True если нет TenderView, False если есть | Invariant | TenderViewService |
