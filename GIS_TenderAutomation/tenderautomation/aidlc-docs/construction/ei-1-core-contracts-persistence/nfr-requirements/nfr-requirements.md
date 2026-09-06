# EI-1 Non-Functional Requirements

## Scope

Эти NFR относятся к Core readiness orchestration, domain contracts, persistence
и V3 projection. Конкретные HTTP/browser budgets адаптеров будут уточнены в EI-2,
а user-facing response/ZIP budgets — в EI-3.

## Performance and capacity

### NFR-EI1-01: Batch bound

- Один request содержит не более 50 уникальных tender IDs.
- Deduplication выполняется до DB/V3/network work.
- Превышение limit отклоняется до запуска инспекции.

### NFR-EI1-02: Concurrency

- Не более четырёх live inspections выполняются одновременно в одном request.
- Concurrency limiter охватывает все площадки суммарно, чтобы невозможно было
  получить четыре операции на каждый adapter одновременно.
- DB/V3-only работа не занимает inspection permit.

### NFR-EI1-03: Latency budgets

- Timeout одной внешней inspection operation: максимум 30 секунд.
- Deadline всей readiness operation: максимум 120 секунд.
- Cached single-tender preparation без network I/O: p95 не более 2 секунд в
  production-like integration environment.
- При исчерпании общего deadline незавершённые candidates получают `unverified`;
  ready/archive outcomes уже завершённых candidates сохраняются.

### NFR-EI1-04: Retry policy

- Внутри пользовательского export request автоматические retries отсутствуют.
- Один candidate вызывает не более одной inspection attempt.
- Повторная проверка выполняется новым request либо плановым reconciliation flow.

## Reliability and data integrity

### NFR-EI1-05: Transaction boundary

- Каждый inspection result применяется отдельной атомарной PostgreSQL transaction.
- Сбой одного tender не откатывает результаты других tender в batch.
- Transaction обновляет только allowlisted inspection/enrichment columns и не
  затрагивает workflow status или qualification fields.

### NFR-EI1-06: Idempotency

- Повторное применение идентичного verified result не меняет observable business
  fields, content hash или updated_at после первого применения.
- Reprocessing одного request не создаёт duplicate outcome entries после ID
  deduplication.

### NFR-EI1-07: Fail-closed behavior

- Contract, DB, timeout, auth, CAPTCHA и network failures не дают ready outcome.
- External failure не создаёт inactive procedure state.
- Unknown state не интерпретируется как active или archive.

### NFR-EI1-08: Time correctness

- Все persisted/check timestamps timezone-aware и нормализованы к UTC.
- Clock инъецируется в decision functions для deterministic TTL/deadline tests.
- TTL граница: `<24h` fresh, `>=24h` stale.

### NFR-EI1-09: Migration compatibility

- Migration только добавляет columns с nullable/default-compatible semantics.
- Старый application image может читать таблицу после upgrade.
- Upgrade тестируется от текущего Alembic head; downgrade path компилируется и
  документируется, но application rollback не требует немедленного downgrade.

## Scalability

### NFR-EI1-10: Bounded horizontal behavior

- Readiness service не хранит cross-request in-memory state.
- Semaphore и adapter sessions request-scoped.
- Межпроцессная координация не требуется: row updates атомарны и затрагивают
  allowlisted columns; verified results применяются монотонно по `attempted_at`,
  поэтому порядок завершения concurrent requests не затирает более свежие данные.
- Масштабирование выше 50 tender/request не входит в эту итерацию и требует
  background job/queue design.

## Security

### NFR-EI1-11: Typed input and least data access

- Core принимает typed `ExportRequest` и `TenderInspectionResult`.
- Batch range проверяется повторно как defense in depth.
- Raw provenance ограничивается namespace/size; он не управляет именами ORM fields.

### NFR-EI1-12: Sensitive-data exclusion

- DTO, outcomes и logs не содержат passwords, tokens, cookies, session state,
  raw HTTP bodies или tender description text.
- Safe error categories используются вместо exception messages от площадок/DB.

### NFR-EI1-13: Auditability

- Structured log event включает correlation/request context, tender ID, platform,
  outcome, inspection source, duration и safe error category.
- Логи не являются источником business truth; persisted timestamps/provenance
  позволяют проверить последнее успешное состояние.

## Observability

### NFR-EI1-14: Required metrics/log aggregates

На request завершающем event фиксируются:

- requested и unique count;
- ready/archived/unverified/ineligible/missing counts;
- cache-hit/live-inspection counts;
- total duration и timeout flag;
- counts по safe external error categories.

Запрещено включать title, description, credentials или response body.

## Maintainability and quality

### NFR-EI1-15: Type and dependency boundaries

- Core не импортирует FastAPI/Jinja2/concrete adapters.
- Public DTO и repository/service signatures проходят strict project mypy gate.
- Новые production dependencies не добавляются без отдельного решения.

### NFR-EI1-16: Test quality

- Example tests покрывают каждое критическое BR/AC.
- Hypothesis реализует TP-01–TP-09 с shrinking и воспроизводимым CI seed.
- Integration tests покрывают Alembic upgrade, per-tender transaction isolation и
  V3 projection.
- Общая line coverage проекта остаётся не ниже 60%.

## Availability and usability

### NFR-EI1-17

- Новый availability SLO для приложения не вводится.
- Outage площадки деградирует только readiness конкретных candidates и не
  повреждает подтверждённые данные.
- UI/accessibility находятся в EI-3; EI-1 предоставляет stable safe reason codes.

## Security Baseline compliance

| Rule | Статус EI-1 | Обоснование |
|---|---|---|
| SECURITY-01 | Без изменений | Новое хранилище не создаётся; existing PostgreSQL posture сохраняется |
| SECURITY-02 | N/A | Network intermediaries не создаются |
| SECURITY-03 | Соответствует | Structured logging и sensitive-data exclusion обязательны |
| SECURITY-04 | N/A | EI-1 не отдаёт HTML |
| SECURITY-05 | Соответствует | Typed input, range validation, allowlisted persistence |
| SECURITY-06 | N/A | IAM/policies не меняются |
| SECURITY-07 | N/A | Network topology не меняется |
| SECURITY-08 | N/A для Core | Route authorization принадлежит EI-3 |
| SECURITY-09 | Соответствует | Safe error categories без internal details |
| SECURITY-10 | Без изменений | Existing pinned dependency/scanner/SBOM gates обязательны |
| SECURITY-11 | Соответствует | Batch/concurrency/deadline ограничивают abuse |
| SECURITY-12 | Соответствует | Credentials отсутствуют в Core DTO/logs |
| SECURITY-13 | Соответствует | Typed/allowlisted state updates защищают data integrity |
| SECURITY-14 | Без изменений | Existing monitoring; required aggregates добавляются |
| SECURITY-15 | Соответствует | DB/contract/external errors fail closed; transactions isolated |

Блокирующих Security findings нет.

## PBT compliance

- PBT-01: TP-01–TP-09 определены в Functional Design.
- PBT-02: N/A для EI-1; JSONL/ZIP round-trip принадлежит EI-3.
- PBT-03: archive, TTL, merge, failure и partition invariants обязательны.
- PBT-04: repository merge idempotency обязательна.
- PBT-05: eligibility oracle обязателен.
- PBT-06: verified/failure state command sequence является обязательным candidate.
- PBT-07: reusable domain/time strategies обязательны.
- PBT-08: shrinking и reproducible seed обязательны.
- PBT-09: Hypothesis уже выбран и остаётся framework.
- PBT-10: critical paths имеют example tests вместе с PBT.

Блокирующих PBT findings нет.
