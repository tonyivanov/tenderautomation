# Unit of Work Story Map — TenderAutomation

## Маппинг User Stories → Units

| Story | Название | Фаза MVP | Unit 1 | Unit 2 | Unit 3 | Unit 4 |
|---|---|:---:|:---:|:---:|:---:|:---:|
| US-01 | Автоматизированный сбор тендеров | 1 | ◐ инфраструктура | ● полностью | | |
| US-02 | Квалификационная фильтрация | 1 | ● полностью | | | |
| US-03 | Скачивание данных для AI-анализа | 1+2 | ◐ JSONL-генерация | | ● UI + скачивание | |
| US-04 | Просмотр тендеров в веб-интерфейсе | 2+3 | | | ● полностью | ◐ уведомления |
| US-05 | Загрузка результата AI-анализа | 2 | | | ● полностью | |
| US-06 | Принятие решений и лог | 2 | | | ● полностью | |
| US-07 | История обработанных тендеров | 2 | | | ● полностью | |

**Легенда**: ● — основная реализация в этом unit; ◐ — частичная реализация (инфраструктура или UI-часть)

---

## Детализация по unit'ам

### Unit 1: Core Library — покрытые истории

**US-01 (частично)** — CollectionService, PipelineOrchestrator, CLI entry point
- `CollectionService.run_all()` — оркестрация сбора
- `PipelineOrchestrator.run()` — полный цикл cron
- `TenderRepository.save_batch()` — сохранение в PostgreSQL
- Scheduler infrastructure (cron job definition)

**US-02 (полностью)** — QualificationEngine, QualificationService
- `QualificationEngine.apply_tier1_batch()` — keyword-скоринг
- `QualificationService.qualify_pending()` — оркестрация квалификации
- `QualifiedLogRepository.append_batch()` — запись в JSONL
- YAML-фильтры: расширенный формат (категории, веса, логические операторы)

**US-03 (частично)** — JSONL-генерация и AGENTS.md
- `QualifiedLogRepository` — хранит JSONL-данные для экспорта
- `TenderModel` — схема данных, от которой зависит формат JSONL
- AGENTS.md создаётся как статический файл в корне репозитория

---

### Unit 2: Platform Adapters — покрытые истории

**US-01 (полностью)** — реализация сбора с обеих площадок
- `B2BCenterAdapter`: HTML-скрейпинг, антибот-паузы, защита от шумных выдач
- `BidzaarAdapter`: JSON API, JWT-аутентификация из `.env`
- `AdapterRegistry`: загрузка дескрипторов, инстанцирование
- YAML-дескрипторы: `b2bcenter/descriptor.yaml`, `bidzaar/descriptor.yaml`

---

### Unit 3: Web Application — покрытые истории

**US-03 (UI-часть)** — скачивание JSONL + AGENTS.md
- `ExportService.build_export_bundle()` — формирование ZIP
- `TenderRouter` — эндпоинт `GET /export` (все новые) и `POST /export` (выбранные)
- Шаблон с кнопкой «Скачать для AI-анализа» и чекбоксами выбора тендеров

**US-04 (полностью)** — просмотр списка и карточки тендера
- `TenderRouter` — `GET /tenders`, `GET /tenders/{id}`
- Jinja2-шаблоны: список с красной точкой, карточка (стандартный уровень)
- `TenderRepository.mark_viewed()` — снятие индикатора «новый»

**US-05 (полностью)** — загрузка результата AI-анализа в карточку
- `ActionRouter` — `POST /tenders/{id}/analysis`
- Форма в карточке: эшелон (select), текст обоснования, AI-инструмент (optional)
- `TenderRepository.save_analysis()`

**US-06 (полностью)** — принятие решений и лог
- `ActionRouter` — `POST /tenders/{id}/action`
- Кнопки: «Взять в работу», «Отклонить», «Отложить» + поле заметки
- `TenderRepository.save_action()` + `ActionLogRepository.append()`

**US-07 (полностью)** — история обработанных тендеров
- `HistoryRouter` — `GET /history`
- Jinja2-шаблон: таблица с фильтрами (площадка, статус, период, пользователь)
- `TenderRepository.get_history(filters)`

---

### Unit 4: Notification Service — покрытые истории

**US-04 (частично)** — уведомления (FR-09)
- `TelegramNotifier.send_new_tenders_alert()` — при событии `tenders_qualified`
- `EmailDigest.send()` — ежедневный дайджест (отдельный cron)
- Конфигурация: токен Telegram, SMTP, recipients — из `.env`

---

## Acceptance Criteria → Unit mapping

| AC / Сценарий | Unit |
|---|---|
| Расписание cron настраивается без изменения кода | Unit 1 (PipelineOrchestrator CLI) |
| При ошибке на одной площадке сбор продолжается | Unit 1 (CollectionService.run_all) |
| YAML-фильтры редактируются без перезапуска | Unit 1 (QualificationEngine.load_rules) |
| JSONL: одна строка = один тендер, валидный JSON | Unit 1 (QualifiedLogRepository) + Unit 3 (ExportService) |
| AGENTS.md — LLM-agnostic | Unit 3 (статический файл + ExportService) |
| Веб-интерфейс требует авторизации | Unit 3 (SessionAuth) |
| Непросмотренные тендеры — красная точка | Unit 3 (TenderRouter + mark_viewed) |
| Выборочный экспорт тендеров | Unit 3 (ExportService + UI) |
| AI-анализ сохраняется, виден всем | Unit 3 (ActionRouter + TenderRepository) |
| Лог JSONL поддерживает конкурентную запись | Unit 3 (ActionLogRepository, file append) |
| Telegram-уведомление при новых тендерах | Unit 4 (TelegramNotifier) |
| Ежедневный email-дайджест | Unit 4 (EmailDigest) |
| Новая площадка — только дескриптор + адаптер | Unit 2 (AdapterRegistry + PlatformAdapter ABC) |

---

## Покрытие историй по unit'ам (сводка)

| Unit | Покрывает (полностью или частично) | Не покрывает |
|---|---|---|
| Unit 1: Core | US-01◐, US-02●, US-03◐ | US-04, US-05, US-06, US-07 |
| Unit 2: Adapters | US-01● | US-02–07 |
| Unit 3: Web App | US-03●, US-04●, US-05●, US-06●, US-07● | US-01, US-02 |
| Unit 4: Notifications | US-04◐ | US-01, US-02, US-03, US-05, US-06, US-07 |

**Проверка**: все 7 историй покрыты хотя бы одним unit'ом. ✓

---

# Export Integrity — Requirements to Unit Map

User Stories для этой итерации были обоснованно пропущены; mapping использует
утверждённые functional/non-functional requirements и acceptance criteria.

## Functional requirements

| Requirement | EI-1 Core | EI-2 Adapters | EI-3 Web/export |
|---|:---:|:---:|:---:|
| FR-01 Guaranteed AI methodology | | | Primary |
| FR-02 Prompt version and integrity | | | Primary |
| FR-03 Classification context | V3 projection and DTO | | JSONL/manifest |
| FR-04 Live enrichment | Orchestration/persistence | Platform extraction | Trigger/result UX |
| FR-05 Freshness and archive | State/predicate | Source verification | List/export behavior |
| FR-06 Single and bulk semantics | Preparation outcomes | | HTTP/ZIP behavior |
| FR-07 Export contract completeness | Export DTO | Provenance fields | JSONL schema |
| FR-08 Documents excluded | | | Manifest flag and instructions |

## Non-functional requirements

| Requirement | EI-1 Core | EI-2 Adapters | EI-3 Web/export |
|---|:---:|:---:|:---:|
| NFR-01 Bounded external calls | Concurrency orchestration | Timeout/retry-safe clients | Batch bounds |
| NFR-02 Security | Fail-closed normalized state | Secret-safe I/O | Auth/input/safe errors |
| NFR-03 Observability | Outcome events | Source/error category | Aggregate export logs |
| NFR-04 Compatibility | Additive migration/fields | Stable contract | Additive JSONL and route |
| NFR-05 Quality | Core tests/PBT | Adapter regressions | Full suite/Docker/smoke |

## Acceptance criteria

| AC | Primary owner | Supporting owner |
|---|---|---|
| AC-01 Docker ZIP has nonempty `AGENTS.md` | EI-3 | — |
| AC-02 Missing/empty template fails without ZIP | EI-3 | — |
| AC-03 Prompt hash equals manifest hash | EI-3 | — |
| AC-04 `filtered` + V3 P2 exports both contexts | EI-3 | EI-1 |
| AC-05 Incomplete active card is enriched with accurate warnings | EI-2 | EI-1, EI-3 |
| AC-06 Expired/closed/cancelled/404 archives and is excluded | EI-1 | EI-2, EI-3 |
| AC-07 Timeout/401/403/CAPTCHA blocks without archive | EI-2 | EI-1, EI-3 |
| AC-08 Bulk includes only verified active records with summary | EI-3 | EI-1 |
| AC-09 ZIP states source documents are absent | EI-3 | — |
| AC-10 Full tests/security/coverage ≥60% | EI-3 | EI-1, EI-2 |

## Security ownership

| Control group | Owner | Evidence target |
|---|---|---|
| Normalized state and fail-closed decisions | EI-1 | domain/repository tests |
| External authentication, timeout and secret-safe errors | EI-2 | adapter tests and logs |
| Route auth, ID bounds, safe 409/503 | EI-3 | web integration tests |
| Prompt/data integrity and supply-chain image checks | EI-3 | hash, Docker, SBOM, scans |

## PBT ownership

| Property | Owner |
|---|---|
| Inspection persistence idempotency | EI-1 |
| Archive predicate preserves workflow status | EI-1 |
| External failure never normalizes to inactive | EI-1 + EI-2 |
| Platform status normalization stays in allowed enum | EI-2 |
| JSONL round-trip preserves contract fields | EI-3 |
| Prompt SHA-256 matches manifest | EI-3 |
| ZIP contains exactly the required core members and nonempty prompt | EI-3 |

## Coverage verification

- FR-01 through FR-08: all assigned.
- NFR-01 through NFR-05: all assigned.
- AC-01 through AC-10: all have primary owners.
- Notifications and document downloading: intentionally unassigned because they
  are outside the approved scope.
- Dependency direction: EI-1 → EI-2 → EI-3, with no cyclic ownership.
