# NFR Design Plan — Unit 1: Core Library

## Статус выполнения

- [x] Шаг 1: Ответы получены и проанализированы
- [x] Шаг 2: nfr-design-patterns.md — паттерны устойчивости, безопасности, производительности
- [x] Шаг 3: logical-components.md — логические компоненты и их взаимодействие

---

## Уже зафиксированные паттерны (вопросы не нужны)

| Паттерн | Решение | Источник |
|---|---|---|
| Retry / Resilience | 3× exponential backoff (1s/2s/4s), skip on failure | BR-13, business-logic-model.md |
| Connection Pool | SQLAlchemy `pool_size=5`, context manager | nfr-requirements.md |
| Security input validation | `yaml.safe_load()`, `json.loads()`, SQLAlchemy ORM (parameterized) | SECURITY-13, tech-stack-decisions.md |
| Log sanitization | No credentials/tokens/PII in log records | SECURITY-03 |
| Config validation | pydantic-settings: fail-fast at startup если .env неполный | BR-21 |
| JSONL append atomicity | `write + flush + fsync` | nfr-requirements.md |
| Sync/Async | Core sync, FastAPI оборачивает через `run_in_executor` | Q5:C |
| JSONL rotation | Monthly files `tenders_YYYY-MM.jsonl` | Q4:B |

---

## Уточняющие вопросы

### Q1: Транзакция в save_batch()
Какой scope транзакции при сохранении пакета тендеров?

A) Одна транзакция на весь пакет — всё или ничего (атомарность, но при ошибке теряем весь пакет)
B) Транзакция на каждый тендер отдельно — частичный успех (при ошибке одного — остальные сохраняются)
C) Savepoint: один тендер — одна точка сохранения внутри общей транзакции (PostgreSQL SAVEPOINT)
X) Другое (опишите после [Answer]:)

[Answer]: B

---

### Q2: Уникальность тендера — DB constraint или application-level?
Как обеспечить уникальность по `(platform, external_id)` при конкурентной записи?

A) Только DB UNIQUE constraint на `id` (= `{platform}_{external_id}`) — PostgreSQL сам отклонит дубль, приложение ловит exception
B) DB UNIQUE constraint + `INSERT ... ON CONFLICT DO UPDATE` (UPSERT на SQL-уровне) — атомарно и эффективно
C) Только application-level SELECT → INSERT/UPDATE — без DB constraint
X) Другое (опишите после [Answer]:)

[Answer]: B
