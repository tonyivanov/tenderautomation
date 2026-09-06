# Units of Work — TenderAutomation

Порядок разработки: строго последовательный (1 → 2 → 3 → 4).
Тип проекта: brownfield, монорепо (`src/`).

---

## Unit 1: Core Library

**Пакет**: `src/core/`
**Порядок**: 1 (блокирующий — все остальные unit'ы зависят от его интерфейсов)

### Ответственность
Ядро системы: унифицированные модели данных, абстрактный интерфейс платформ, движок квалификации, репозитории доступа к данным, EventBus, оркестрирующие сервисы и CLI-точка входа для cron.

### Компоненты
| Компонент | Тип | Описание |
|---|---|---|
| `TenderModel` | Pydantic model | Унифицированное представление тендера |
| `TenderAction` | Pydantic model | Решение специалиста + AI-анализ |
| `PlatformDescriptor` | Pydantic model | Конфигурация площадки из YAML |
| `PlatformAdapter` | ABC | Контракт для всех адаптеров |
| `QualificationEngine` | Stateless service | Tier 1 keyword-скоринг |
| `TenderRepository` | Repository | CRUD PostgreSQL |
| `QualifiedLogRepository` | Repository | Append-only JSONL |
| `ActionLogRepository` | Repository | Append-only JSONL |
| `EventBus` | In-process pub/sub | Связь pipeline → notifications |
| `CollectionService` | Service | Оркестрация сбора с площадок |
| `QualificationService` | Service | Оркестрация квалификации |
| `PipelineOrchestrator` | Service | Полный цикл: сбор → квалификация → события |

### Deliverables
- `src/core/models/` — data models (Pydantic)
- `src/core/adapters/base.py` — PlatformAdapter ABC
- `src/core/repositories/` — TenderRepository, QualifiedLogRepository, ActionLogRepository
- `src/core/services/` — CollectionService, QualificationService, PipelineOrchestrator
- `src/core/events/bus.py` — EventBus
- `src/core/cli.py` — CLI entry point (`python -m core.cli run-pipeline`)
- `filters/keywords.yaml` — обновлённый формат фильтров
- Database schema: PostgreSQL migrations (tenders, users, actions, sessions)
- Tests: unit tests + Hypothesis PBT для QualificationEngine, JSONL сериализации

### User Stories покрытые
US-01 (частично: инфраструктура сбора), US-02 (квалификация), US-03 (частично: генерация JSONL)

---

## Unit 2: Platform Adapters

**Пакет**: `src/adapters/`
**Порядок**: 2 (зависит от Unit 1: PlatformAdapter ABC, TenderModel, PlatformDescriptor)
**Состав**: B2BCenterAdapter + BidzaarAdapter разрабатываются вместе как один unit

### Ответственность
Реализация контракта PlatformAdapter для B2B-Center (HTML-скрейпинг) и Bidzaar (JSON API). Автоматическая аутентификация из `.env`. Реестр адаптеров с загрузкой YAML-дескрипторов.

### Компоненты
| Компонент | Тип | Описание |
|---|---|---|
| `AdapterRegistry` | Registry | Загрузка дескрипторов, инстанцирование адаптеров |
| `B2BCenterAdapter` | Concrete adapter | HTML-скрейпинг b2b-center.ru, антибот-паузы |
| `BidzaarAdapter` | Concrete adapter | JSON API bidzaar.com, JWT-аутентификация |

### Deliverables
- `src/adapters/registry.py`
- `src/adapters/b2bcenter/adapter.py` + `descriptor.yaml`
- `src/adapters/bidzaar/adapter.py` + `descriptor.yaml`
- Tests: unit tests + Hypothesis PBT для маппинга полей (round-trip: RawTender → Tender → fields)

### User Stories покрытые
US-01 (полностью: сбор с обеих площадок, автоаутентификация)

---

## Unit 3: Web Application

**Пакет**: `src/web/`
**Порядок**: 3 (зависит от Unit 1: TenderRepository, ActionLogRepository, ExportService logic)

### Ответственность
FastAPI-приложение с Jinja2 SSR. Аутентификация специалистов через сессии. Просмотр квалифицированных тендеров, скачивание JSONL+AGENTS.md, загрузка AI-анализа, фиксация решений, история.

### Компоненты
| Компонент | Тип | Описание |
|---|---|---|
| `FastAPIApp` | Application | Инициализация, middleware, регистрация роутеров |
| `SessionAuth` | Middleware + dependency | Cookie-based аутентификация |
| `TenderRouter` | Router | Список, карточка, просмотр (Jinja2) |
| `ActionRouter` | Router | Решения специалиста, загрузка AI-анализа |
| `HistoryRouter` | Router | История обработанных тендеров |
| `ExportService` | Service | JSONL + AGENTS.md для скачивания |

### Deliverables
- `src/web/app.py` — FastAPI factory
- `src/web/auth.py` — SessionAuth
- `src/web/routers/` — tenders.py, actions.py, history.py
- `src/web/services/export.py` — ExportService
- `src/web/templates/` — Jinja2 HTML-шаблоны
- `AGENTS.md` — LLM-agnostic инструкция для AI-агентов
- Tests: unit tests + Hypothesis PBT для ExportService (JSONL round-trip)

### User Stories покрытые
US-03 (скачивание JSONL+AGENTS.md), US-04 (просмотр, индикатор новых, уведомления badge), US-05 (загрузка AI-анализа в карточку), US-06 (решения + лог), US-07 (история)

---

## Unit 4: Notification Service

**Пакет**: `src/notifications/`
**Порядок**: 4 (зависит от Unit 1: EventBus, TenderRepository)

### Ответственность
Отправка Telegram-уведомлений при появлении новых квалифицированных тендеров (через EventBus) и ежедневного email-дайджеста (отдельный cron job).

### Компоненты
| Компонент | Тип | Описание |
|---|---|---|
| `NotificationHandler` | Event subscriber | Подписка на EventBus, вызов TelegramNotifier |
| `TelegramNotifier` | Notifier | Отправка сообщений через Telegram Bot API |
| `EmailDigest` | Notifier | Формирование и отправка email-дайджеста (SMTP) |

### Deliverables
- `src/notifications/handler.py`
- `src/notifications/telegram.py`
- `src/notifications/email_digest.py`
- `src/notifications/cli.py` — CLI entry point (`python -m notifications.cli send-digest`)
- Tests: unit tests для форматирования сообщений; mock Telegram/SMTP API

### User Stories покрытые
US-04 (частично: Telegram-уведомление + email-дайджест как часть FR-09)

---

## Сводная таблица

| Unit | Пакет | Порядок | Зависит от | Stories |
|---|---|---|---|---|
| Core Library | `src/core/` | 1 | — | US-01 (часть), US-02, US-03 (часть) |
| Platform Adapters | `src/adapters/` | 2 | Unit 1 | US-01 (полностью) |
| Web Application | `src/web/` | 3 | Unit 1 | US-03, US-04, US-05, US-06, US-07 |
| Notification Service | `src/notifications/` | 4 | Unit 1 | US-04 (часть) |

---

# Export Integrity — Units of Work текущей итерации

Все три unit являются логическими модулями существующего монолита, поставляются
в одной ветке и одном Merge Request, но проходят последовательно отдельные
design/code checkpoints.

## EI-1: Core Contracts & Persistence

**Порядок**: 1, блокирует EI-2 и EI-3.

**Пакеты**: `src/core/`, `migrations/versions/`.

### Ответственность

- Domain models `ProcedureState`, inspection/error DTO и export preparation DTO.
- Расширение `PlatformAdapter` единым async inspection contract.
- Аддитивная PostgreSQL migration и ORM/model mapping.
- Идемпотентное repository-применение inspection result.
- Единый archive predicate, не изменяющий пользовательский workflow status.
- `V3ExportProjection` с judge override и queue mapping.
- `ExportReadinessService` и composition wiring abstractions.

### Deliverables

- Core models и публичные exports.
- `PlatformAdapter.inspect_tender` contract с safe default.
- Alembic migration для procedure metadata.
- Repository methods для export candidates и atomic inspection update.
- V3 projection и readiness orchestration.
- Unit/example/PBT tests для transitions, idempotency и DTO invariants.

### Entry criteria

- Утверждённые requirements и Application Design.
- Существующая migration head `0002` и baseline repository tests проходят.

### Exit criteria

- Migration upgrade проходит и остаётся обратно совместимой со старым image.
- Core API типизирован и не зависит от FastAPI или concrete adapters.
- Archive predicate и external-failure invariants покрыты тестами.

## EI-2: Platform Inspection

**Порядок**: 2, зависит от EI-1 и блокирует EI-3.

**Пакеты**: `src/adapters/b2bcenter/`, `src/adapters/bidzaar/`, adapter tests.

### Ответственность

- Реализация `inspect_tender` для B2B-Center и Bidzaar.
- Извлечение buyer, budget, deadline, description, published_at и procedure state.
- Нормализация active/closed/completed/cancelled/not_found.
- Отделение 404 от timeout/network/auth/CAPTCHA.
- Сохранение обоих B2B-Center access modes: endpoint и Playwright.
- Запрет LLM-вызовов и persistence writes внутри adapters.

### Deliverables

- Две concrete реализации inspection contract.
- Переиспользуемые parsers/status normalization helpers.
- Provenance для каждого полученного поля и источника.
- Example tests для каждого исхода и PBT normalization invariants.
- Regression tests для endpoint и Playwright B2B-Center.

### Entry criteria

- EI-1 domain/adapter contract стабилен и покрыт тестами.

### Exit criteria

- Оба адаптера возвращают один и тот же normalized result contract.
- 404 создаёт `not_found`; временные/авторизационные сбои не создают archive state.
- Endpoint и Playwright тестируются независимо.

## EI-3: Async Export & Packaging

**Порядок**: 3, зависит от EI-1 и EI-2.

**Пакеты**: `src/web/`, `prompts/`, `Dockerfile`, tests/smoke/docs.

### Ответственность

- Async export route и валидированный `ExportRequest`.
- Dedicated `prompts/tender_analysis_agents.md` и prompt provider.
- Расширенная JSONL схема с legacy/V3/procedure/completeness context.
- `export_manifest.json`, SHA-256 и обязательные ZIP member invariants.
- HTML 409/503 result page и bulk outcome summary.
- Использование V3 projection в list/detail/export без дублирования правил.
- Production-image asset, smoke и user documentation.

### Deliverables

- Async `ExportRouter` и dependency wiring.
- Pure `ExportBundleService` и `TenderAnalysisPromptProvider`.
- Runtime prompt template и обновлённая export schema documentation.
- Result template, Docker copy rule и smoke assertions.
- Example/PBT/integration tests и full Build & Test evidence.

### Entry criteria

- EI-1 readiness/persistence и EI-2 inspection implementations завершены.

### Exit criteria

- Active tender создаёт проверяемый ZIP из трёх обязательных members.
- Inactive и unverified outcomes дают безопасные 409/503 без ZIP.
- Docker/smoke подтверждают непустой prompt и manifest hash.
- Full suite проходит с line coverage не ниже 60%.

## Поставка

- **Ветка/MR**: одна ветка и один Merge Request.
- **Commit boundaries**: EI-1, EI-2, EI-3 и финальная Build & Test evidence.
- **Deployment**: один существующий application image; промежуточных production
  deployments между units нет.
- **Вне scope**: Notifications, document downloader, LLM provider changes,
  отдельный readiness service и новая инфраструктура.
