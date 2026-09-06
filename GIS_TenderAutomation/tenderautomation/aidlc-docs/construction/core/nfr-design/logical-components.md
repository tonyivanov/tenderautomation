# Logical Components — Unit 1: Core Library

## Обзор компонентов

```
src/core/
├── config.py              # Settings (pydantic-settings)
├── logging.py             # JsonFormatter + logger factory
├── db.py                  # SessionFactory (SQLAlchemy engine + SessionLocal)
├── models/
│   ├── tender.py          # TenderModel, TenderStatus, RawTender, ScoredTender
│   ├── action.py          # TenderAction, AnalysisResult
│   └── platform.py        # PlatformDescriptor, PlatformCredentials, AuthSession
├── adapters/
│   └── base.py            # PlatformAdapter ABC
├── repositories/
│   ├── tender.py          # TenderRepository (upsert, qualify, history)
│   ├── qualified_log.py   # QualifiedLogRepository (JSONL append)
│   └── action_log.py      # ActionLogRepository (JSONL append)
├── services/
│   ├── collection.py      # CollectionService
│   ├── qualification.py   # QualificationService + QualificationEngine
│   └── pipeline.py        # PipelineOrchestrator
├── events/
│   └── bus.py             # EventBus
└── cli.py                 # Entry point: python -m core.cli run-pipeline
```

---

## 1. Settings (Конфигурационный синглтон)

**Файл**: `src/core/config.py`
**Тип**: pydantic-settings `BaseSettings`

**Ответственность**:
- Загружает `.env` при первом импорте
- Валидирует все обязательные переменные (`ValidationError` → `sys.exit(1)`)
- Предоставляет типизированный доступ к конфигурации

**Ключевые поля**:
```python
class Settings(BaseSettings):
    # DB
    database_url: str                  # postgresql://user:pass@host/db
    
    # Platform credentials
    b2bcenter_username: str
    b2bcenter_password: str
    bidzaar_username: str
    bidzaar_password: str
    
    # Paths
    data_dir: Path = Path("data")      # директория для JSONL-файлов
    filters_dir: Path = Path("filters") # keywords.yaml, config.yaml
    
    # Pipeline tuning
    qualification_threshold: int = 50
    collection_max_retries: int = 3
    collection_retry_base_sec: float = 1.0
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()  # синглтон на уровне модуля
```

**Использование**: `from core.config import settings`

---

## 2. DB Session Factory

**Файл**: `src/core/db.py`
**Тип**: SQLAlchemy engine + sessionmaker

**Ответственность**:
- Создаёт connection pool к PostgreSQL (один раз при старте)
- Предоставляет `SessionLocal` для контекстных менеджеров
- Не содержит бизнес-логики

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

engine = create_engine(
    settings.database_url,
    pool_size=5,
    max_overflow=2,
    pool_timeout=30,
    pool_pre_ping=True,   # проверка соединения перед выдачей из пула
    connect_args={"sslmode": "require"},  # SECURITY-01
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

class Base(DeclarativeBase):
    pass
```

**Паттерн использования в репозиториях**:
```python
with SessionLocal() as session:
    session.execute(stmt)
    session.commit()
# Соединение автоматически возвращается в пул
```

---

## 3. JSON Log Formatter

**Файл**: `src/core/logging.py`
**Тип**: `logging.Formatter` subclass

**Ответственность**:
- Форматирует записи в JSON (SECURITY-03)
- Маскирует чувствительные ключи в `context` (SECURITY-03)
- Добавляет обязательные поля: `timestamp`, `level`, `logger`, `message`

**Фабричная функция**:
```python
def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    return logger
```

**Использование**: `log = get_logger(__name__)`
**Контекст**: `log.info("collection_done", extra={"context": {"platform": "bidzaar", "count": 42}})`

---

## 4. JSONL File Router

**Встроен в**: `QualifiedLogRepository`, `ActionLogRepository`

**Ответственность**:
- Определяет путь к текущему месячному файлу
- Создаёт директорию при первом обращении
- Возвращает все файлы для чтения (glob)

```python
class JsonlFileRouter:
    def __init__(self, base_name: str, data_dir: Path):
        self.base_name = base_name
        self.data_dir = data_dir

    def current_path(self) -> Path:
        month = datetime.utcnow().strftime("%Y-%m")
        path = self.data_dir / f"{self.base_name}_{month}.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def all_paths(self) -> list[Path]:
        return sorted(self.data_dir.glob(f"{self.base_name}_*.jsonl"))
```

---

## 5. Content Hash Computer

**Встроен в**: `TenderRepository` (вызывается перед upsert)

**Ответственность**:
- Нормализует контентные поля
- Вычисляет SHA-256

```python
import hashlib, json
from decimal import Decimal
from datetime import datetime

def compute_content_hash(title: str, buyer: str | None, budget: Decimal | None,
                          deadline: datetime | None, description: str | None) -> str:
    normalized = {
        "title": (title or "").strip().lower(),
        "buyer": (buyer or "").strip().lower(),
        "budget": f"{budget:.2f}" if budget else "",
        "deadline": deadline.isoformat() if deadline else "",
        "description": (description or "").strip().lower(),
    }
    payload = json.dumps(normalized, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
```

---

## 6. EventBus

**Файл**: `src/core/events/bus.py`

**Ответственность**: in-process pub/sub для связи `PipelineOrchestrator` → `NotificationHandler` без прямой зависимости.

```python
from collections import defaultdict
from typing import Callable

class EventBus:
    def __init__(self):
        self._handlers: dict[str, list[Callable]] = defaultdict(list)

    def subscribe(self, event: str, handler: Callable) -> None:
        self._handlers[event].append(handler)

    def publish(self, event: str, **payload) -> None:
        for handler in self._handlers.get(event, []):
            try:
                handler(**payload)
            except Exception as e:
                log.error("event_handler_failed",
                          extra={"context": {"event": event, "handler": handler.__name__, "error": str(e)}})
                # Ошибка одного обработчика не прерывает остальных
```

**Особенность**: `EventBus` — in-process, не персистентный. Живёт только в рамках одного cron-запуска.

---

## 7. PlatformAdapter ABC

**Файл**: `src/core/adapters/base.py`

Формальный контракт, который **должны реализовать** все адаптеры Unit 2:

```python
from abc import ABC, abstractmethod

class PlatformAdapter(ABC):
    @abstractmethod
    def platform_id(self) -> str: ...

    @abstractmethod
    async def authenticate(self, credentials: PlatformCredentials) -> AuthSession: ...

    @abstractmethod
    async def fetch_new(
        self, session: AuthSession, since: datetime, descriptor: PlatformDescriptor
    ) -> list[RawTender]: ...

    @abstractmethod
    def map_to_tender(self, raw: RawTender, descriptor: PlatformDescriptor) -> Tender: ...
```

**Примечание**: методы `authenticate` и `fetch_new` объявлены `async` (платформенные HTTP-запросы могут быть async в Unit 2), `map_to_tender` — синхронный (CPU-bound маппинг).

---

## Взаимодействие компонентов при запуске pipeline

```
cli.py: python -m core.cli run-pipeline
    │
    ├── Settings()              # pydantic-settings: .env → typed config
    ├── get_logger(__name__)    # JsonFormatter → stdout
    ├── engine = create_engine(settings.database_url)
    │
    └── PipelineOrchestrator(
            collection=CollectionService(registry, TenderRepository),
            qualification=QualificationService(engine, TenderRepository,
                                               QualifiedLogRepository,
                                               settings.filters_dir),
            event_bus=EventBus(),
            notification_handler=NotificationHandler(event_bus)
        ).run()
            │
            ├── CollectionService.run_all()
            │       └── [B2BCenterAdapter, BidzaarAdapter]
            │               → fetch_new() → map_to_tender()
            │               → TenderRepository.save_batch()  [per-tender transactions]
            │                   → INSERT ... ON CONFLICT DO UPDATE
            │
            ├── QualificationService.qualify_pending()
            │       → TenderRepository.get_by_status('pending')  [composite index]
            │       → QualificationEngine.score_tier1() × N      [in-memory]
            │       → TenderRepository.update_qualification()     [per-tender]
            │       → QualifiedLogRepository.append_batch()       [JSONL + fsync]
            │
            └── EventBus.publish('tenders_qualified', count=N)
                    └── NotificationHandler.on_tenders_qualified()
                            └── TelegramNotifier.send_alert()     [Unit 4]
```
