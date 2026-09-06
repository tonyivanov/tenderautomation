# Code Summary — Unit 1: Core Library

## Созданные файлы

### Проект
| Файл | Назначение |
|---|---|
| `pyproject.toml` | Метаданные, зависимости, конфиг mypy/pytest |
| `requirements.txt` | Pinned runtime зависимости |
| `requirements-dev.txt` | Dev зависимости (pytest, hypothesis, mypy) |
| `.env.example` | Шаблон переменных окружения |
| `alembic.ini` | Конфиг Alembic |

### Core Library (`src/core/`)
| Файл | Компонент | Содержание |
|---|---|---|
| `config.py` | Settings | pydantic-settings, fail-fast validation |
| `logging.py` | JsonFormatter | JSON-лог с sanitization чувствительных ключей |
| `db.py` | DB Engine | SQLAlchemy engine, SessionLocal, Base |
| `cli.py` | CLI | Click entry point: `run-pipeline` |
| `models/tender.py` | TenderModel | TenderStatus, RawTender, ScoredTender, content_hash |
| `models/action.py` | TenderAction | AnalysisResult, HistoryFilters |
| `models/platform.py` | PlatformDescriptor | PlatformCredentials, AuthSession |
| `orm/tender.py` | ORM | TenderORM, TenderActionORM, CollectionRunORM |
| `adapters/base.py` | PlatformAdapter | ABC с 4 абстрактными методами |
| `adapters/registry.py` | AdapterRegistry | Реестр адаптеров |
| `repositories/tender.py` | TenderRepository | Upsert (ON CONFLICT), qualify, history, collection_runs |
| `repositories/qualified_log.py` | QualifiedLogRepository | JSONL monthly rotation, fsync |
| `repositories/action_log.py` | ActionLogRepository | JSONL append |
| `services/qualification_engine.py` | QualificationEngine | Tier 1 scoring, load_config, YAML rules |
| `services/qualification.py` | QualificationService | qualify_pending orchestration |
| `services/collection.py` | CollectionService | retry+backoff, run_all |
| `services/pipeline.py` | PipelineOrchestrator | Полный цикл: collect→qualify→event |
| `events/bus.py` | EventBus | In-process pub/sub, error isolation |

### Миграции (`migrations/`)
| Файл | Содержание |
|---|---|
| `env.py` | Alembic environment |
| `script.py.mako` | Template для новых миграций |
| `versions/0001_initial_schema.py` | Таблицы tenders, tender_actions, collection_runs + индексы |

### Фильтры (`filters/`)
| Файл | Содержание |
|---|---|
| `keywords.yaml` | 25+ правил: whitelist (cloud, devops, security, AI, migration) + blacklist |
| `config.yaml` | threshold=50, semantic_profile для AGENTS.md |

### Тесты (`tests/`)
| Файл | Тип | Покрытие |
|---|---|---|
| `test_content_hash.py` | Unit + PBT | Детерминизм, чувствительность к изменениям |
| `test_qualification_engine.py` | Unit + PBT | score≥0, blacklist→0, детерминизм, threshold |
| `test_status_machine.py` | Unit + PBT | Допустимые/недопустимые переходы |
| `test_jsonl_roundtrip.py` | Unit + PBT | Serialize→JSON→parse, обязательные поля |

## Ключевые паттерны

- **SQL UPSERT**: `INSERT ... ON CONFLICT (id) DO UPDATE ... WHERE content_hash != excluded.content_hash`
- **Per-tender transactions**: каждый тендер в save_batch — отдельная сессия/транзакция
- **Monthly JSONL rotation**: `tenders_2026-06.jsonl`, `actions_2026-06.jsonl`
- **Fail-fast config**: pydantic-settings — ValidationError → sys.exit(1) при старте
- **Blacklist priority**: первое совпадение с blacklist → score=0, выход из цикла

## Интерфейс для Unit 2 (Platform Adapters)

Unit 2 реализует `PlatformAdapter` ABC (`src/core/adapters/base.py`):
```python
class MyAdapter(PlatformAdapter):
    def platform_id(self) -> str: return "myplatform"
    async def authenticate(self, credentials) -> AuthSession: ...
    async def fetch_new(self, session, since, descriptor) -> list[RawTender]: ...
    def map_to_tender(self, raw, descriptor) -> TenderModel: ...
```

Регистрация в `src/core/cli.py`:
```python
registry.register(MyAdapter())
```
