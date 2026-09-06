# Components — TenderAutomation

## Структура пакетов

```
src/
├── core/           # Unit 1 — Core Library
├── adapters/       # Unit 2 — Platform Adapters
├── web/            # Unit 3 — Web Application
└── notifications/  # Unit 4 — Notification Service
```

---

## Unit 1: Core Library (`src/core/`)

### `TenderModel`
**Тип**: Data model (Pydantic BaseModel)
**Ответственность**: Унифицированное представление тендера вне зависимости от площадки. Единый контракт для всех слоёв системы.
**Поля**: id, platform, external_id, title, buyer, budget, deadline, description, url, raw_data, prefilter_score, qualification_tier, published_at, collected_at, status

### `PlatformAdapter`
**Тип**: Abstract Base Class (ABC)
**Ответственность**: Контракт для всех адаптеров площадок. Определяет обязательный интерфейс аутентификации, инкрементального сбора и получения деталей тендера.
**Реализации**: `B2BCenterAdapter`, `BidzaarAdapter`

### `PlatformDescriptor`
**Тип**: Data model (Pydantic / dataclass)
**Ответственность**: Загрузка и хранение конфигурации площадки из YAML-дескриптора. Параметры: название, base_url, auth_method, rate_limits, field_mappings.

### `QualificationEngine`
**Тип**: Service component (stateless)
**Ответственность**: Двухуровневая квалификация тендеров. Tier 1: keyword-скоринг по YAML-правилам. Tier 2: формирование семантических правил для AI-агента (включается в AGENTS.md и JSONL).

### `TenderRepository`
**Тип**: Repository (Data Access)
**Ответственность**: CRUD-операции с тендерами и действиями специалистов в PostgreSQL. Не содержит бизнес-логики.

### `QualifiedLogRepository`
**Тип**: Repository (Append-only)
**Ответственность**: Запись квалифицированных тендеров в JSONL-файл (append-only, для истории и экспорта AI-агенту).

### `ActionLogRepository`
**Тип**: Repository (Append-only)
**Ответственность**: Запись действий специалистов (взять/отклонить/отложить) в JSONL-файл.

### `EventBus`
**Тип**: In-process pub/sub
**Ответственность**: Публикация и подписка на события внутри pipeline-процесса (cron-скрипта). Связывает QualificationService с NotificationService без прямой зависимости.
**Ключевые события**: `tenders_qualified`, `collection_complete`, `collection_error`

---

## Unit 2: Platform Adapters (`src/adapters/`)

### `B2BCenterAdapter(PlatformAdapter)`
**Тип**: Concrete adapter
**Ответственность**: Реализация PlatformAdapter для B2B-Center. HTML-скрейпинг поисковой выдачи с антибот-паузами, защита от шумных выдач (>1000 лотов), Playwright-аутентификация (переход на .env credentials).

### `BidzaarAdapter(PlatformAdapter)`
**Тип**: Concrete adapter
**Ответственность**: Реализация PlatformAdapter для Bidzaar. JSON API клиент, JWT-аутентификация по логину/паролю из .env, инкрементальный синк.

### `AdapterRegistry`
**Тип**: Registry / Factory
**Ответственность**: Реестр доступных адаптеров. Загружает YAML-дескрипторы из директории платформ, инстанцирует и возвращает нужный адаптер по имени платформы.

---

## Unit 3: Web Application (`src/web/`)

### `FastAPIApp`
**Тип**: Application entry point
**Ответственность**: Инициализация FastAPI-приложения, регистрация роутеров, middleware, статических файлов и Jinja2-шаблонов.

### `SessionAuth`
**Тип**: Middleware + dependency
**Ответственность**: Session-based аутентификация. Проверка cookie-сессии на каждом защищённом запросе. Логин/логаут эндпоинты.

### `TenderRouter`
**Тип**: FastAPI Router
**Ответственность**: Эндпоинты для работы со списком тендеров, карточкой тендера, фильтрацией, пагинацией. Рендеринг Jinja2-шаблонов.

### `ActionRouter`
**Тип**: FastAPI Router
**Ответственность**: Эндпоинты фиксации решений специалиста (взять/отклонить/отложить) и загрузки результата AI-анализа в карточку тендера.

### `ExportService`
**Тип**: Service component
**Ответственность**: Формирование JSONL-файла с квалифицированными тендерами и AGENTS.md для скачивания специалистом. Поддерживает выборочный и полный экспорт.

### `HistoryRouter`
**Тип**: FastAPI Router
**Ответственность**: Эндпоинты истории обработанных тендеров с фильтрацией и поиском.

---

## Unit 4: Notification Service (`src/notifications/`)

### `TelegramNotifier`
**Тип**: Notifier component
**Ответственность**: Отправка уведомлений в Telegram через Bot API при появлении новых квалифицированных тендеров. Токен и chat_id берутся из .env.

### `EmailDigest`
**Тип**: Notifier component
**Ответственность**: Формирование и отправка ежедневного email-дайджеста со списком новых тендеров. Конфигурация SMTP из .env.

### `NotificationHandler`
**Тип**: Event subscriber
**Ответственность**: Подписывается на события EventBus. При событии `tenders_qualified` вызывает TelegramNotifier. Email-дайджест запускается отдельным cron job.

---

## Export Integrity — дополнение текущей итерации

### `ProcedureState` и `TenderInspectionResult`

**Тип**: Core domain models.

**Назначение**: отделяют состояние процедуры на площадке от пользовательского
workflow-статуса. `ProcedureState` нормализует `unknown`, `active`, `closed`,
`completed`, `cancelled` и `not_found`. `TenderInspectionResult` переносит
результат live-проверки, enrichment-поля, provenance, время проверки и безопасную
категорию внешней ошибки.

### `PlatformAdapter.inspect_tender`

**Тип**: расширение существующего Core ABC.

**Назначение**: единый async-контракт live-инспекции карточки без LLM. B2B-Center
сохраняет оба способа доступа — endpoint и Playwright; Bidzaar использует API и
detail card. Адаптеры возвращают domain result и не изменяют БД напрямую.

### `TenderRepository` — inspection persistence

**Тип**: расширение repository.

**Назначение**: атомарно сохраняет допустимые enrichment-поля, `procedure_state`,
время и источник проверки. Пользовательский `status` не меняется. Повторное
применение одинакового результата должно быть идемпотентным.

### `V3ExportProjection`

**Тип**: read-only Core service/component.

**Назначение**: читает существующий SQLite V3 cache и в одном месте применяет
judge override и правила queue. Возвращает стабильный экспортный view; Web и
ExportService не читают SQLite напрямую.

### `ExportReadinessService`

**Тип**: Core orchestration service.

**Назначение**: загружает кандидатов, переиспользует одну authenticated session
на площадку, запускает bounded live inspection, сохраняет результат, определяет
active/archive/unverified и присоединяет V3 context. Не формирует HTTP-ответ или
ZIP.

### `TenderAnalysisPromptProvider`

**Тип**: deterministic asset provider.

**Назначение**: загружает versioned runtime-шаблон
`prompts/tender_analysis_agents.md`, подставляет semantic profile, отклоняет
пустой/неполный шаблон и возвращает содержимое, версию и SHA-256. Корневой
`AGENTS.md` больше не является runtime-источником AI ZIP.

### `ExportBundleService`

**Тип**: Web application service без внешнего I/O.

**Назначение**: сериализует только подготовленные active candidates, создаёт
JSONL, `export_manifest.json` и ZIP. Проверяет обязательные ZIP members и
целостность prompt hash перед возвратом bundle.

### `ExportRouter`

**Тип**: authenticated FastAPI router.

**Назначение**: валидирует ID и batch bounds, ожидает
`ExportReadinessService.prepare`, возвращает ZIP либо безопасную HTML-страницу:
409 для неактивного результата и 503 для неподтверждённого внешнего сбоя.

### `ExportResultTemplate`

**Тип**: Jinja2 error/result view.

**Назначение**: сообщает, почему ZIP не создан, не раскрывая токены, внутренние
пути, stack trace или тело ответа площадки; предоставляет ссылку назад к карточке
или списку.
