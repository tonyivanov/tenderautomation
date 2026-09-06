# Code Generation Plan — Unit 1: Core Library

## Контекст Unit

**Workspace root**: `/Users/gitinsky/Projects/GitInSky/Marketing/TenderAutomation`
**Тип проекта**: Brownfield — новая `src/` структура внутри существующего репозитория
**Application code**: `src/core/` (новые файлы; существующий код в `Разбор тендеров/` не изменяется)
**Tests**: `tests/unit/core/`
**Migrations**: `migrations/`
**Filters**: `filters/`
**Documentation**: `aidlc-docs/construction/core/code/`

**Истории**: US-01◐ (инфраструктура сбора), US-02● (квалификация), US-03◐ (JSONL)

**Зависимости Unit 1**: нет (Unit 1 — базовый, все остальные зависят от него)

---

## Статус выполнения

### Шаг 1: Структура проекта и зависимости
- [x] 1.1 `pyproject.toml` — метаданные, зависимости, mypy, pytest конфиг
- [x] 1.2 `requirements.txt` (lock) + `requirements-dev.txt`
- [x] 1.3 `.env.example` — шаблон обязательных переменных
- [x] 1.4 `src/core/__init__.py`, `src/__init__.py`

### Шаг 2: Конфигурация
- [x] 2.1 `src/core/config.py` — Settings (pydantic-settings), fail-fast validation

### Шаг 3: Логирование
- [x] 3.1 `src/core/logging.py` — JsonFormatter, get_logger(), log sanitization

### Шаг 4: Модели данных (Pydantic)
- [x] 4.1 `src/core/models/tender.py` — TenderModel, TenderStatus, RawTender, ScoredTender, CollectionResult
- [x] 4.2 `src/core/models/action.py` — TenderAction, AnalysisResult, HistoryFilters
- [x] 4.3 `src/core/models/platform.py` — PlatformDescriptor, PlatformCredentials, AuthSession
- [x] 4.4 `src/core/models/__init__.py`

### Шаг 5: ORM-модели и DB (SQLAlchemy)
- [x] 5.1 `src/core/db.py` — engine, SessionLocal, Base
- [x] 5.2 `src/core/orm/tender.py` — TenderORM, TenderActionORM, CollectionRunORM (SQLAlchemy mapped classes)
- [x] 5.3 `src/core/orm/__init__.py`

### Шаг 6: Alembic — миграции
- [x] 6.1 `migrations/env.py`, `migrations/script.py.mako` — alembic setup
- [x] 6.2 `migrations/versions/0001_initial_schema.py` — таблицы + индексы
- [x] 6.3 `alembic.ini`

### Шаг 7: Platform Adapter ABC
- [x] 7.1 `src/core/adapters/__init__.py`
- [x] 7.2 `src/core/adapters/base.py` — PlatformAdapter ABC
- [x] 7.3 `src/core/adapters/registry.py` — AdapterRegistry (заглушка для Unit 2)

### Шаг 8: Репозитории
- [x] 8.1 `src/core/repositories/__init__.py`
- [x] 8.2 `src/core/repositories/tender.py` — TenderRepository (upsert ON CONFLICT, qualify, history)
- [x] 8.3 `src/core/repositories/qualified_log.py` — QualifiedLogRepository (JSONL monthly rotation)
- [x] 8.4 `src/core/repositories/action_log.py` — ActionLogRepository (JSONL monthly rotation)

### Шаг 9: Движок квалификации + конфиг фильтров
- [x] 9.1 `src/core/services/qualification_engine.py` — QualificationEngine (score_tier1, load_rules)
- [x] 9.2 `filters/keywords.yaml` — обновлённый формат (term, weight, category, match_type)
- [x] 9.3 `filters/config.yaml` — threshold и прочие параметры

### Шаг 10: Сервисы
- [x] 10.1 `src/core/services/__init__.py`
- [x] 10.2 `src/core/services/qualification.py` — QualificationService
- [x] 10.3 `src/core/services/collection.py` — CollectionService (retry + backoff)
- [x] 10.4 `src/core/services/pipeline.py` — PipelineOrchestrator

### Шаг 11: EventBus
- [x] 11.1 `src/core/events/__init__.py`
- [x] 11.2 `src/core/events/bus.py` — EventBus (subscribe, publish, error isolation)

### Шаг 12: CLI entry point
- [x] 12.1 `src/core/cli.py` — `run-pipeline` команда (Click или argparse)

### Шаг 13: Тесты (pytest + Hypothesis)
- [x] 13.1 `tests/__init__.py`, `tests/unit/__init__.py`, `tests/unit/core/__init__.py`
- [x] 13.2 `tests/conftest.py` — фикстуры (тестовая БД, settings override)
- [x] 13.3 `tests/unit/core/test_content_hash.py` — детерминизм, различие хешей
- [x] 13.4 `tests/unit/core/test_qualification_engine.py` — PBT: score≥0, blacklist→0, детерминизм
- [x] 13.5 `tests/unit/core/test_status_machine.py` — PBT: только допустимые переходы
- [x] 13.6 `tests/unit/core/test_jsonl_roundtrip.py` — PBT: round-trip serialize→parse
- [x] 13.7 `tests/unit/core/test_tender_repository.py` — PBT: upsert idempotence

### Шаг 14: Документация
- [x] 14.1 `aidlc-docs/construction/core/code/code-summary.md` — сводка сгенерированных файлов

---

## Трассировка историй

| История | Шаги |
|---|---|
| US-01◐ (инфраструктура сбора) | 1, 2, 3, 5, 6, 7, 10.3, 10.4, 11, 12 |
| US-02● (квалификация) | 4, 8.2, 9, 10.2 |
| US-03◐ (JSONL) | 8.3, 9.2, 9.3 |

---

## Интерфейсы для Unit 2 (Platform Adapters)

Unit 2 реализует `PlatformAdapter` ABC из шага 7.2. После Unit 1 Unit 2 получает:
- `PlatformAdapter` ABC с полными сигнатурами
- `TenderModel`, `RawTender`, `PlatformDescriptor`, `PlatformCredentials`, `AuthSession`
- `TenderRepository.save_batch()` для сохранения результатов сбора
- `CollectionService` для интеграции адаптеров в pipeline
