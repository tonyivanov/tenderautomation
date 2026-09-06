# EI-1 NFR Design Patterns — Core Contracts & Persistence

## Design basis

Дизайн реализует утверждённые NFR-EI1-01–NFR-EI1-17 и ответы Q1–Q5:

- batch содержит не более 50 уникальных IDs;
- одновременно выполняются не более четырёх внешних операций на request;
- timeout одной внешней операции — 30 секунд, всего readiness flow — 120 секунд;
- retries внутри export request отсутствуют;
- каждый tender сохраняется отдельной атомарной транзакцией;
- sync PostgreSQL/SQLite I/O изолируется через `asyncio.to_thread`;
- concurrent results применяются монотонно по `attempted_at`;
- provenance ограничен allowlist, 16 ключами и 8 KiB;
- ошибка V3 cache не превращается в ложный classification result.

Resiliency Baseline extension для этой итерации отключён. Ниже описаны только
patterns, необходимые утверждённым timeout, cleanup и fail-closed требованиям;
retries, circuit breaker и background queue не добавляются.

## Pattern 1: Request-scoped bounded fan-out

`ExportReadinessService` сначала валидирует и дедуплицирует request, затем
создаёт не более одной candidate task на уникальный tender. Все внешние операции
площадок используют один request-scoped `asyncio.Semaphore(4)` независимо от
platform.

Правила:

1. Limit 50 проверяется до PostgreSQL, SQLite и network I/O.
2. Classification eligibility и сохранённый expired deadline проверяются до
   live inspection.
3. Ineligible, missing и уже expired candidates не занимают внешний permit.
4. Lazy authentication и сама inspection получают permit отдельно; permit не
   удерживается во время ожидания per-platform session lock.
5. Одна authenticated session создаётся на platform в рамках request и
   закрывается при normal completion, timeout и cancellation.
6. DB/V3 operations не занимают inspection permit; для них используется
   отдельный request-scoped I/O limiter с максимум четырьмя worker calls.
7. Результаты собираются по исходному stable index, а не по completion order.

Такой fan-out ограничивает нагрузку и сохраняет детерминированный порядок при
частично успешном batch.

## Pattern 2: Hierarchical deadline and cooperative cancellation

Readiness использует абсолютный UTC deadline, рассчитанный один раз от
`ExportRequest.requested_at`. Внутренний work window заканчивается не позднее
чем за 5 секунд до общего 120-секундного deadline; остаток резервируется для
отмены tasks, закрытия sessions и завершения уже начатых коротких транзакций.

Для каждой external operation effective timeout равен меньшему из 30 секунд и
оставшегося work budget. Новая операция не запускается при исчерпанном budget.

Structured-concurrency правила:

- candidate wrapper преобразует обычные adapter/contract errors в typed outcome,
  чтобы ошибка одного tender не отменяла siblings;
- `asyncio.CancelledError` не перехватывается как обычная ошибка;
- при internal batch timeout coordinator отменяет pending candidate tasks и
  ожидает их cleanup;
- уже завершённые ready/archived/unverified outcomes и commits сохраняются;
- отменённые internal-deadline candidates получают `unverified` с
  `batch_timeout`;
- caller cancellation отменяет и очищает tasks, после чего пробрасывается выше;
  service не создаёт detached/background tasks.

Retries и backoff внутри request отсутствуют. Новый request является новой
attempt.

## Pattern 3: Blocking I/O isolation

Существующие SQLAlchemy repository и `sqlite3` APIs остаются синхронными.
`BlockingIOBridge` вызывает их через `asyncio.to_thread`, не меняя runtime stack.

Обязательные ограничения worker callable:

- SQLAlchemy session либо SQLite connection создаётся, используется и закрывается
  целиком в одном worker call;
- session/connection/ORM instance не передаётся между threads;
- наружу возвращается detached `TenderModel`, `V3ExportContext` или typed error;
- worker не получает credentials и не пишет raw exception text в outcomes;
- новый worker call не создаётся после исчерпания request budget;
- PostgreSQL statement/connection timeout и SQLite busy timeout ограничиваются
  оставшимся budget, чтобы cancellation cleanup не оставлял долгую работу после
  request;
- request-scoped I/O limiter не использует inspection permits и не хранит
  cross-request state.

Candidate load предпочтительно выполняется одним repository call, а V3 projection
читает contexts batch-операцией с одной short-lived read connection. Это
уменьшает thread scheduling и connection churn без нового cache layer.

## Pattern 4: Per-tender atomic monotonic merge

`TenderRepository.apply_inspection` открывает отдельную transaction для одного
tender, блокирует только целевую row на время merge и применяет allowlisted
columns.

### Verified result

1. Сравнить timezone-aware `result.attempted_at` с сохранённым
   `procedure_checked_at`.
2. Более старый result вернуть как stale no-op и прочитать актуальную row.
3. При равном timestamp и одинаковом normalized fingerprint выполнить
   idempotent no-op.
4. При равном timestamp и различном fingerprint не выбирать результат по commit
   order: выполнить fail-closed no-op, записать safe `result_conflict` event и
   вернуть `unverified` вызывающему request.
5. Более новый result обновляет procedure metadata и только non-null verified
   enrichment fields.
6. Workflow `status`, qualification и matched keywords не входят в update set.
7. `content_hash` и business `updated_at` меняются только при фактическом
   изменении enrichment fields.

### Failed result

Failure не меняет `procedure_state`, `procedure_checked_at` и verified enrichment.
Он может монотонно увеличить только `procedure_last_attempt_at` и заменить
`procedure_error_category`, если attempt не старше сохранённой. Transaction error
приводит к rollback и `unverified`; он не откатывает commits других tenders.

Этот compare-and-apply pattern исключает ситуацию, когда медленно завершившаяся
старая инспекция перезаписывает более свежую.

## Pattern 5: Validated bounded provenance

`TenderInspectionResult` валидирует `raw_data_updates` до repository call.
Разрешены только scalar JSON values (`str`, `int`, `float`, `bool`, `null`) и
следующие keys:

- `procedure_status_raw`;
- `deadline_raw`;
- `published_at_raw`;
- `buyer_reference`;
- `source_revision`;
- `inspection_mode`;
- `http_status`;
- `canonical_url`;
- `active_marker`;
- `parser_version`;
- `response_etag`;
- `response_last_modified`;
- `detail_id`.

Одновременно действуют пределы: не более 16 keys и не более 8 KiB canonical
UTF-8 JSON. Raw HTML, response body, cookies, tokens, passwords, headers и nested
objects запрещены. Нарушение является `contract_violation`, не сохраняется и
даёт `unverified`, а не archive/ready.

Repository повторно использует собственный allowlist ORM columns; provenance
keys никогда не интерпретируются как имена полей модели.

## Pattern 6: Tri-state V3 projection failure

V3 lookup не должен сворачивать три разных состояния в `None`:

- `found(context)` — V3 verdict/queue рассчитаны;
- `not_found` — валидный cache read, записи нет;
- `unavailable(error_category)` — SQLite отсутствует, повреждён, заблокирован
  сверх timeout либо query contract нарушен.

При `unavailable`:

- legacy `qualified` продолжает readiness path с безопасным
  `v3_context_status=unavailable`;
- legacy `filtered` получает `unverified/v3_unavailable`, поскольку P1/P2 нельзя
  ни подтвердить, ни опровергнуть;
- candidate не получает ложный `ineligible`;
- сбой одного lookup не обрушает batch;
- external inspection не запускается для filtered candidate с неразрешённой
  eligibility.

`not_found` сохраняет утверждённое правило BR-01: legacy `qualified` допустим,
legacy `filtered` — `ineligible`.

## Pattern 7: Fail-closed outcome partition

Все safe failures завершаются ровно одним outcome и не создают inactive state.

| Событие | Outcome | Persistence |
|---|---|---|
| Tender отсутствует | `missing` | нет |
| Classification доказанно не подходит | `ineligible` | нет |
| Сохранённый/verified deadline истёк | `archived` | verified state сохраняется |
| Verified closed/completed/cancelled/not_found | `archived` | verified state сохраняется |
| Auth/network/CAPTCHA/platform timeout | `unverified` | только монотонная attempt metadata |
| Internal batch timeout | `unverified` | завершённые commits сохраняются |
| Adapter/DTO/provenance violation | `unverified` | result не применяется |
| V3 unavailable для legacy filtered | `unverified` | нет classification mutation |
| PostgreSQL apply failure | `unverified` | rollback конкретного tender |
| Fresh or newly verified active | `ready` | prepared model возвращается |

Unknown state никогда не интерпретируется как ready или archive. Partition
conservation и stable ordering проверяются после завершения orchestration.

## Pattern 8: Structured low-cardinality observability

Service использует существующий structured logger и safe enums. Candidate event
содержит request/correlation ID, tender ID, platform, outcome, source,
cache/live marker, duration и safe error category. Он не содержит title,
description, credentials, cookie, response body, raw provenance или exception
message.

Один завершающий request event содержит:

- requested/unique counts;
- ready/archived/unverified/ineligible/missing counts;
- cache-hit/live-inspection counts;
- total duration и batch-timeout flag;
- counts по allowlisted error categories.

Логирование не является business source of truth. Последнее успешное состояние,
timestamps и bounded provenance хранятся в PostgreSQL.

## Security compliance

| Rule | Статус | Design control |
|---|---|---|
| SECURITY-01 | Соответствует, без topology change | Нового store/transport нет; existing PostgreSQL/SQLite posture сохраняется |
| SECURITY-02 | N/A | EI-1 не создаёт network intermediary |
| SECURITY-03 | Соответствует | Structured safe candidate/request events |
| SECURITY-04 | N/A | EI-1 не формирует HTML response |
| SECURITY-05 | Соответствует | Typed request/result, batch bounds, provenance и SQL allowlists |
| SECURITY-06 | N/A | IAM/policy не меняются |
| SECURITY-07 | N/A | Network topology не меняется |
| SECURITY-08 | N/A для Core | Authenticated route остаётся ответственностью EI-3 |
| SECURITY-09 | Соответствует | Safe error categories без stack/internal details |
| SECURITY-10 | Соответствует | Новых dependencies нет; existing scanners/SBOM остаются gates |
| SECURITY-11 | Соответствует | Bounds, dual validation и misuse handling |
| SECURITY-12 | Соответствует | Credentials живут только в session factory/scope и не попадают в DTO/logs |
| SECURITY-13 | Соответствует | Typed validation, monotonic merge и auditable metadata |
| SECURITY-14 | Соответствует, existing control | Aggregate events добавляются; central retention/alerts не меняются |
| SECURITY-15 | Соответствует | Explicit error mapping, rollback, cancellation cleanup и fail closed |

Blocking Security findings отсутствуют.

## PBT preservation

| Rule | Статус | NFR design obligation |
|---|---|---|
| PBT-01 | Соответствует | TP-01–TP-09 остаются source properties |
| PBT-02 | N/A для EI-1 | JSONL/manifest/ZIP round-trip принадлежит EI-3 |
| PBT-03 | Соответствует | TTL, archive, failure safety и partition invariants сохранены |
| PBT-04 | Соответствует | Monotonic merge и повторное применение проверяются на idempotency |
| PBT-05 | Соответствует | Eligibility и concurrent apply сравниваются с простым model oracle |
| PBT-06 | Соответствует | Sequence model включает verified, failure, stale и equal-conflict commands |
| PBT-07 | Соответствует | Нужны reusable tender/result/time/provenance strategies |
| PBT-08 | Соответствует | Shrinking и воспроизводимый seed остаются обязательными |
| PBT-09 | Соответствует | Hypothesis выбран в Tech Stack Decisions |
| PBT-10 | Соответствует | Critical timeout/race/failure cases получают example tests вместе с PBT |

Blocking PBT findings отсутствуют.
