# Tech Stack Decisions — Unit 1: Core Library

## Сводная таблица

| Слой | Библиотека / инструмент | Версия | Обоснование |
|---|---|---|---|
| ORM | SQLAlchemy | 2.x | Q1:A — высокоуровневый, автомаппинг, работает с Alembic |
| DB driver | psycopg2-binary | ≥2.9 | Стандартный sync-драйвер для PostgreSQL |
| Миграции | Alembic | ≥1.13 | Q2:A — нативная интеграция с SQLAlchemy ORM |
| Модели | Pydantic | v2 | Application Design — валидация, сериализация, JSON |
| Config / .env | pydantic-settings | v2 | Pydantic-native, type-safe, читает .env |
| Логирование | stdlib `logging` + JSON formatter | built-in | Q3:A — без доп. зависимостей; JSON formatter — собственный или `python-json-logger` |
| Тестирование | pytest + Hypothesis | pytest≥8, Hypothesis≥6 | NFR-05 / PBT-09 — стандарт для Python PBT |
| Type checking | mypy | ≥1.9 | Статический анализ, совместим с Pydantic v2 |
| YAML-парсинг | PyYAML | ≥6.0 | Чтение `keywords.yaml`, `config.yaml`; только `safe_load()` |
| .env загрузка | python-dotenv | ≥1.0 | Загрузка `.env` в os.environ до импорта pydantic-settings |

## Детали ключевых решений

### SQLAlchemy ORM 2.x + Alembic

**Почему ORM, а не Core или raw SQL:**
- Автомаппинг упрощает работу с `Tender`, `TenderAction`, `CollectionRun`
- Alembic автогенерирует миграции из моделей (`alembic revision --autogenerate`)
- SQLAlchemy 2.x поддерживает both sync и async API — оставляет открытой дверь для будущего async (Unit 3 уже использует sync через `run_in_executor`)

**Паттерн использования (sync):**
```python
# Session factory через sessionmaker
engine = create_engine(DATABASE_URL, pool_size=5, max_overflow=2)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

# Context manager в каждом вызове репозитория
with SessionLocal() as session:
    ...
```

**Структура миграций:**
```
migrations/
├── env.py
├── script.py.mako
└── versions/
    ├── 0001_initial_schema.py
    └── 0002_add_matched_keywords.py
```

### Pydantic v2 (модели + конфиг)

**Модели** (`src/core/models/`): `BaseModel` для `Tender`, `TenderAction`, `RawTender`, etc.

**Конфиг** (`src/core/config.py`):
```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str
    data_dir: Path = Path("data")
    
    class Config:
        env_file = ".env"
```

### Stdlib logging + JSON formatter

**Формат лог-записи:**
```json
{
  "timestamp": "2026-06-03T08:00:00Z",
  "level": "INFO",
  "logger": "core.pipeline",
  "message": "Collection complete",
  "context": {"platform": "bidzaar", "new_count": 42}
}
```

**Конфигурация:**
```python
import logging, json

class JsonFormatter(logging.Formatter):
    def format(self, record):
        return json.dumps({
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "context": getattr(record, "context", {}),
        }, ensure_ascii=False)
```

**Правило SECURITY-03**: `exc_info` в логе разрешён (stacktrace для отладки), но `record.args` не должен содержать пароли или токены.

### JSONL ротация (ежемесячная)

**Именование файлов:**
```
data/
├── tenders_2026-06.jsonl   # текущий
├── tenders_2026-05.jsonl   # предыдущий
└── actions_2026-06.jsonl
```

**Логика выбора файла при записи:**
```python
from datetime import datetime
from pathlib import Path

def current_jsonl_path(base_name: str, data_dir: Path) -> Path:
    month = datetime.utcnow().strftime("%Y-%m")
    return data_dir / f"{base_name}_{month}.jsonl"
```

**Чтение (для экспорта/анализа)**: glob по `data/{base_name}_*.jsonl`, сортировка по имени.

### pytest + Hypothesis

**Структура тестов:**
```
tests/
├── unit/
│   ├── test_qualification_engine.py   # PBT для scoring
│   ├── test_tender_repository.py      # PBT для upsert idempotence
│   ├── test_jsonl_roundtrip.py        # PBT round-trip
│   └── test_status_machine.py        # PBT для transitions
└── conftest.py                        # фикстуры, тестовая БД
```

**Пример PBT-теста:**
```python
from hypothesis import given, settings
from hypothesis import strategies as st
from src.core.services.qualification import QualificationEngine

@given(score=st.integers(min_value=0))
def test_score_always_nonnegative(score):
    # score_tier1 никогда не возвращает отрицательное значение
    result, _ = engine.score_tier1(tender_with_score(score), rules)
    assert result >= 0
```

## Минимальный `requirements.txt` Core Library

```
SQLAlchemy>=2.0
psycopg2-binary>=2.9
alembic>=1.13
pydantic>=2.0
pydantic-settings>=2.0
PyYAML>=6.0
python-dotenv>=1.0
pytest>=8.0
hypothesis>=6.0
mypy>=1.9
```

## Что NOT используется

| Библиотека | Причина отказа |
|---|---|
| asyncpg / SQLAlchemy async | Core sync; async в FastAPI через `run_in_executor` |
| structlog / loguru | Не нужны: stdlib logging достаточен + меньше зависимостей |
| Celery / Redis | Нет очередей задач: cron достаточен |
| pickle | Запрещён SECURITY-13 |
| `yaml.load()` | Запрещён: только `yaml.safe_load()` |
