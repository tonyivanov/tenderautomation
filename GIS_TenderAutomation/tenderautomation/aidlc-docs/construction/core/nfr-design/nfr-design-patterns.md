# NFR Design Patterns — Unit 1: Core Library

## Resilience Patterns

### 1. Per-Tender Transaction Isolation

**Паттерн**: Independent Transactions per Item

**Применение**: `TenderRepository.save_batch()`

**Дизайн**:
```
for tender in batch:
    try:
        with SessionLocal() as session:   # новая сессия = новая транзакция
            session.execute(upsert_stmt)
            session.commit()
            result.count_success()
    except Exception as e:
        result.count_failed(tender.id, str(e))
        log.warning("tender_save_failed", context={"tender_id": tender.id})
        continue  # не прерываем пакет
```

**Результат**: `CollectionResult(new=N, updated=M, skipped=K, failed=F)` — каждый тендер независим.

**Обоснование**: потеря одного тендера из-за транзитной ошибки не должна блокировать сохранение остальных 99.

---

### 2. Retry with Exponential Backoff

**Паттерн**: Retry + Circuit Break (simplified)

**Применение**: `CollectionService.run_for_platform()`

```
MAX_ATTEMPTS = 3
delays = [1, 2, 4]  # секунды

for attempt, delay in enumerate(delays, 1):
    try:
        return adapter.fetch_new(...)
    except AuthError:
        log_collection_run(status='auth_error')
        raise  # не retryable
    except (NetworkError, HTTP5xx):
        if attempt == MAX_ATTEMPTS:
            log_collection_run(status='failed')
            return CollectionError(platform)
        sleep(delay)
```

**Нет полного Circuit Breaker**: при 3 последовательных сбоях площадка пропускается, следующий cron-запуск попробует снова. Состояние CB не персистируется между запусками (cron = новый процесс).

---

### 3. Fail-Fast Config Validation

**Паттерн**: Eager Validation / Guard Clause

**Применение**: запуск cron-скрипта `python -m core.cli run-pipeline`

```python
# В Settings (pydantic-settings) — проверка при import
class Settings(BaseSettings):
    database_url: str           # обязательное — ValidationError если отсутствует
    b2bcenter_username: str
    b2bcenter_password: str
    bidzaar_username: str
    bidzaar_password: str
    data_dir: Path = Path("data")
    qualification_threshold: int = 50

# При старте CLI:
try:
    settings = Settings()
except ValidationError as e:
    log.critical("config_invalid", context={"errors": e.errors()})
    sys.exit(1)
```

**Результат**: неполная конфигурация → немедленный выход с понятным сообщением, а не криптическая ошибка в середине работы.

---

### 4. Graceful Degradation

**Паттерн**: Bulkhead (изоляция платформ друг от друга)

**Применение**: `CollectionService.run_all()`

```
results = []
for platform_id in registry.get_all_platform_ids():
    try:
        result = await run_for_platform(platform_id)
        results.append(result)
    except (CollectionError, CollectionAuthError) as e:
        results.append(CollectionFailure(platform_id, e))
        # pipeline продолжается

return CollectionSummary(results)
# QualificationService видит только тендеры которые успешно сохранены
```

---

## Security Patterns

### 5. Parameterized Query (SQL Injection Prevention)

**Паттерн**: Parameterized Statements via ORM

SQLAlchemy ORM генерирует parameterized SQL автоматически. Для upsert используется PostgreSQL-специфичный диалект:

```python
from sqlalchemy.dialects.postgresql import insert

stmt = insert(TenderModel).values(**tender_dict)
stmt = stmt.on_conflict_do_update(
    index_elements=["id"],
    set_={
        "title": stmt.excluded.title,
        "buyer": stmt.excluded.buyer,
        "budget": stmt.excluded.budget,
        "deadline": stmt.excluded.deadline,
        "description": stmt.excluded.description,
        "raw_data": stmt.excluded.raw_data,
        "content_hash": stmt.excluded.content_hash,
        "updated_at": stmt.excluded.updated_at,
    },
    where=(TenderModel.content_hash != stmt.excluded.content_hash)
    # Если content_hash совпадает — DO NOTHING (skip)
)
```

Никакой конкатенации строк в SQL. Все значения — bind parameters.

---

### 6. Input Sanitization Gateway

**Паттерн**: Validation at Entry Point

Все внешние данные проходят через единственную точку входа перед сохранением:

```
RawTender (platform API/HTML)
    → adapter.map_to_tender()       # маппинг полей
    → Pydantic TenderModel(**data)  # валидация типов, форматов
    → content_hash computation      # нормализация перед хешированием
    → TenderRepository.save_batch() # запись в БД
```

`raw_data` (оригинальный ответ площадки) хранится как PostgreSQL JSONB — никогда не исполняется, только читается.

---

### 7. Log Sanitization

**Паттерн**: Sensitive Data Masking in Formatter

Кастомный JSON-форматтер маскирует чувствительные ключи в поле `context`:

```python
SENSITIVE_KEYS = frozenset({"password", "token", "cookie", "secret", "auth", "credential"})

class JsonFormatter(logging.Formatter):
    def _sanitize(self, obj: dict) -> dict:
        return {
            k: "***" if any(s in k.lower() for s in SENSITIVE_KEYS) else v
            for k, v in obj.items()
        }

    def format(self, record):
        context = self._sanitize(getattr(record, "context", {}))
        return json.dumps({
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "context": context,
        }, ensure_ascii=False)
```

---

### 8. Safe Deserialization

**Паттерн**: Allowlist Deserialization

| Тип данных | Метод | Запрещено |
|---|---|---|
| JSONL-файлы | `json.loads(line)` | `pickle.loads()` |
| YAML-конфиг | `yaml.safe_load(f)` | `yaml.load(f)` без Loader |
| DB raw_data | SQLAlchemy JSONB автодекодирование | `eval()`, `exec()` |

---

## Performance Patterns

### 9. SQL UPSERT (ON CONFLICT DO UPDATE)

**Паттерн**: Atomic Upsert

Единственный SQL-запрос вместо SELECT + (INSERT или UPDATE):

```sql
-- Генерируется SQLAlchemy:
INSERT INTO tenders (id, platform, title, ...)
VALUES ($1, $2, $3, ...)
ON CONFLICT (id) DO UPDATE SET
    title = EXCLUDED.title,
    content_hash = EXCLUDED.content_hash,
    updated_at = EXCLUDED.updated_at,
    ...
WHERE tenders.content_hash != EXCLUDED.content_hash
-- Если hash совпадает — строка не изменяется (DO NOTHING по условию WHERE)
```

**Выигрыш**: нет race condition при конкурентной записи; нет round-trip SELECT перед каждым INSERT.

---

### 10. Batch Scoring (In-Memory Processing)

**Паттерн**: Bulk Fetch + In-Memory Processing

```
# Одна DB-операция для получения всех pending
pending_tenders = TenderRepository.get_by_status('pending')

# In-memory scoring — без DB round-trip per tender
scored = [engine.score_tier1(t, rules) for t in pending_tenders]

# Одна bulk UPDATE или per-tender UPDATE (отдельные транзакции)
for tender, (score, keywords, tier) in zip(pending_tenders, scored):
    TenderRepository.update_qualification(tender.id, score, tier, keywords)
```

---

### 11. JSONL Streaming Append

**Паттерн**: Append-Only Write with Group Fsync

```python
def append_batch(self, tenders: list[ScoredTender]) -> None:
    path = self._current_month_path()
    with open(path, 'a', encoding='utf-8') as f:
        for tender in tenders:
            line = tender.model_dump_json(exclude={'raw_data'})
            f.write(line + '\n')
        f.flush()
        os.fsync(f.fileno())  # один fsync на весь пакет
```

`fsync` один раз после пакета (не per-line) — баланс между надёжностью и I/O.

---

### 12. DB Index Strategy

```sql
-- Основные индексы (в Alembic миграции):
CREATE UNIQUE INDEX ix_tenders_id ON tenders (id);
CREATE INDEX ix_tenders_platform_status ON tenders (platform, status);
CREATE INDEX ix_tenders_collected_at ON tenders (collected_at DESC);
CREATE INDEX ix_collection_runs_platform_status ON collection_runs (platform, status, completed_at DESC);
```

Запросы `get_by_status('pending')` и `get_qualified(platform=X)` используют composite index `(platform, status)`.
