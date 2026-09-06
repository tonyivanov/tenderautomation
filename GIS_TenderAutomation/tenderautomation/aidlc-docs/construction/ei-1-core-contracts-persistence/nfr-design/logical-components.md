# EI-1 Logical Components — Core Contracts & Persistence

## Boundary

EI-1 добавляет logical components внутри существующего Core и persistence слоя.
Он не создаёт новый process, queue, cache, database или deployment unit. FastAPI,
Jinja2 и ZIP остаются за границей EI-1; LLM не вызывается.

## Component inventory

| Logical component | Proposed location | Responsibility |
|---|---|---|
| Export domain contracts | `src/core/models/export.py` or existing models package | Procedure/V3/request/result enums and immutable DTOs |
| Export request guard | Pure helper in Core service/model | Validate max 50, timezone, ID uniqueness and stable order |
| `V3ExportProjection` | `src/core/services/v3_export.py` | Read-only found/not-found/unavailable projection with centralized judge/queue rules |
| `BlockingIOBridge` | Private helper in `export_readiness.py` | Bounded `asyncio.to_thread` calls with deadline propagation |
| `PlatformSessionScope` | Private request-scoped helper | Lazy one-session-per-platform creation, reuse and cleanup |
| `InspectionCoordinator` | Private helper in `export_readiness.py` | Shared external semaphore, timeouts, tasks and cancellation |
| Inspection result validator | Export model/service boundary | Verify enum consistency, timestamps and bounded provenance |
| Inspection persistence API | `src/core/repositories/tender.py` | Candidate reads and atomic monotonic per-tender apply |
| Readiness decision policy | Pure functions in Core service | Eligibility, TTL, archive, completeness and partition rules |
| `ExportReadinessService` | `src/core/services/export_readiness.py` | Compose components and return `ExportPreparationResult` |
| Readiness telemetry | Existing Core structured logger | Candidate events and one aggregate request event |

Logical helpers may remain private functions/classes where a separate public type
does not improve testing. Public boundaries are domain DTOs,
`V3ExportProjection`, repository methods and `ExportReadinessService.prepare`.

## Dependency rules

| Consumer | May depend on | Must not depend on |
|---|---|---|
| Domain contracts | Pydantic/dataclass, datetime, enums | FastAPI, SQLAlchemy, adapters |
| Decision policy | Domain contracts, injected clock | DB, SQLite, network, Web |
| V3 projection | `sqlite3`, V3 model/queue rules | Web templates, adapters, PostgreSQL writes |
| Blocking I/O bridge | `asyncio`, sync callable ports | ORM details, credentials, Web |
| Session scope | Adapter registry/session factory | Repository, V3 cache, ZIP |
| Inspection coordinator | Adapter interface, session scope, clock | Concrete adapter modules, FastAPI |
| Repository | SQLAlchemy ORM/PostgreSQL, domain contracts | HTTP semantics, CAPTCHA parsing, V3 cache |
| Readiness service | All Core ports above | Jinja2, ZIP, LLM clients, concrete adapters |

Concrete adapters are registered in the composition root. EI-2 implements the
`inspect_tender` contract; Core does not import those implementations.

## Public contracts

### `V3ExportProjection`

The projection exposes a typed batch operation in addition to a single lookup:

```python
class V3ExportProjection:
    def get_many(
        self, candidates: tuple[TenderModel, ...]
    ) -> dict[str, V3LookupResult]: ...
```

`V3LookupResult` is one of `found`, `not_found` or `unavailable`. A cache
exception is never represented as ordinary absence. The method creates and
closes one short-lived read connection inside its worker call and uses
parameterized SQL.

### `TenderRepository`

```python
class TenderRepository:
    def get_export_candidates(
        self, tender_ids: tuple[str, ...] | None, *, limit: int
    ) -> list[TenderModel]: ...

    def apply_inspection(
        self, result: TenderInspectionResult
    ) -> InspectionApplyResult: ...
```

`InspectionApplyResult` distinguishes `applied`, `idempotent`, `stale`,
`conflict` and `missing`, and returns the detached current model when available.
It does not leak SQLAlchemy exceptions.

### `ExportReadinessService`

```python
class ExportReadinessService:
    async def prepare(
        self, request: ExportRequest
    ) -> ExportPreparationResult: ...
```

The service depends on repository/projection/adapter/session abstractions and an
injectable UTC clock. It returns all five outcome collections and aggregate
statistics; it does not create an HTTP response or ZIP.

## Resource ownership

| Resource | Owner | Lifetime | Cleanup |
|---|---|---|---|
| Candidate tasks | `InspectionCoordinator` | One readiness request | Cancel and await in coordinator exit |
| External semaphore | `InspectionCoordinator` | One readiness request | Released by `async with` |
| I/O semaphore | `BlockingIOBridge` | One readiness request | Released by `async with` |
| Adapter session | `PlatformSessionScope` | Lazy, one per platform/request | Async/sync close through context manager |
| Per-platform init lock | `PlatformSessionScope` | One platform/request | Released before inspection permit acquisition |
| SQLAlchemy session | Repository worker callable | One repository call/transaction | Commit or rollback, then close in same thread |
| SQLite connection | V3 projection worker callable | One batch lookup | Close in same thread |
| Clock/deadline | Readiness service | One request | Immutable values |

Ни один resource не кэшируется между requests. Credentials входят только в
injected session factory and are never stored in request/result objects.

## Orchestration sequence

1. Request guard validates timezone-aware request, max 50 and deduplicates IDs
   while preserving order.
2. Blocking I/O bridge loads all candidates in one repository worker call.
3. V3 projection performs one batch read and returns typed lookup states.
4. Decision policy assigns missing/ineligible/already-expired candidates without
   network calls.
5. Coordinator creates tasks only for eligible candidates requiring inspection.
6. Session scope lazily authenticates once per platform under the shared external
   limit and reuses the session.
7. Coordinator calls `inspect_tender` under the same limit and per-operation
   deadline.
8. Result validator rejects invalid state/provenance before persistence.
9. Blocking I/O bridge invokes one atomic repository apply per valid result.
10. Decision policy evaluates the detached current model and produces exactly one
    outcome per candidate.
11. Coordinator cancels pending tasks at the work deadline, drains cleanup and
    assigns `batch_timeout` outcomes.
12. Service orders outcomes by stable request/repository index, verifies partition
    conservation, emits aggregate telemetry and returns the result.

## Session initialization and failures

`PlatformSessionScope` uses a per-platform lock only to prevent duplicate lazy
authentication inside one request. The flow is:

1. Read cached request-scoped session or cached safe auth failure.
2. If absent, enter the platform init lock.
3. Recheck the cache.
4. Acquire the shared external permit, authenticate within the remaining
   operation budget, then release the permit.
5. Cache either the session or a safe failure category for sibling candidates.

Auth failure maps affected candidates to `unverified/auth_error`; it does not
create procedure state. Endpoint/Playwright/API/detail-card choice remains inside
the EI-2 adapter. For B2B-Center both endpoint and Playwright modes remain valid
and are exposed only through allowlisted `source`/`inspection_mode` provenance.

## Persistence interaction

The repository worker owns the complete transaction:

1. Open session and select the target row for update.
2. Compare `attempted_at` with current successful/attempt timestamps.
3. Handle stale/idempotent/equal-conflict without business mutation.
4. Merge only verified non-null enrichment values and normalized procedure fields.
5. For failure, update only monotonic attempt metadata.
6. Recompute `content_hash` and `updated_at` only when business content changes.
7. Commit and convert ORM row to detached domain model.
8. On exception, rollback, map to safe `db_error`, and close the session.

Cross-request external calls are intentionally not locked. Row-level transaction
serialization plus timestamp comparison protects stored truth without holding a
database lock during network I/O.

## Timeout and cancellation interaction

`InspectionCoordinator` maintains the absolute batch deadline and a cleanup
reserve. Candidate tasks catch and return typed external failures, but allow
cancellation to propagate. On internal deadline it:

1. snapshots completed results;
2. cancels remaining candidate tasks;
3. awaits task and session cleanup within the reserved budget;
4. preserves completed commits;
5. creates deterministic `batch_timeout` outcomes for pending candidates.

Blocking worker calls are started only with positive remaining budget and must
apply driver-level timeouts. This prevents a cancelled coroutine from leaving an
unbounded SQL/SQLite operation behind.

## Error boundary matrix

| Boundary | Safe category | Owner | Result |
|---|---|---|---|
| Request validation | `invalid_request` | Request guard | Reject before I/O |
| V3 read | `v3_unavailable` | V3 projection | Qualified continues; filtered unverified |
| Adapter registration | `unknown_platform` | Coordinator | Candidate unverified |
| Authentication | `auth_error` | Session scope | Platform candidates unverified |
| External call | `network_error`, `captcha`, `operation_timeout` | Coordinator | Candidate unverified |
| Result contract | `contract_violation` | Result validator | No persistence, unverified |
| Concurrent equal result | `result_conflict` | Repository | No overwrite, unverified |
| PostgreSQL | `db_error` | Repository/bridge | Rollback candidate, unverified |
| Batch deadline | `batch_timeout` | Coordinator | Pending candidate unverified |

Only confirmed expired/inactive source truth can produce archive. Infrastructure
and contract failures never do.

## Integration contracts for subsequent units

### EI-2 Platform Inspection

- Implements async `inspect_tender` and returns immutable
  `TenderInspectionResult`.
- Does not write PostgreSQL or V3 cache.
- Returns safe error category instead of raw exception/response body.
- Closes page/client resources when cancelled.
- Preserves B2B-Center endpoint and Playwright acquisition modes.

### EI-3 Async Export & Packaging

- Awaits only `ExportReadinessService.prepare` and never calls concrete adapters.
- Serializes `ready` records only.
- Maps archived/ineligible to safe 409 behavior and unverified failures to safe
  503 behavior according to the approved Web design.
- Uses outcome reason codes and V3 lookup status without parsing logs/exceptions.

## Verification obligations

- Unit tests: semaphore bound, stable ordering, timeout mapping, V3 tri-state,
  provenance bounds and pure decision rules.
- PostgreSQL integration: additive migration, row locking, monotonic stale/equal/
  newer results, rollback isolation and content-hash idempotency.
- Async integration: event loop remains responsive while repository/V3 workers
  are active; sessions close on timeout/cancellation; no detached tasks remain.
- Property tests: TP-01–TP-09 plus concurrent apply oracle and provenance boundary
  strategies.
- Quality gates: strict Core mypy scope and project line coverage at least 60%.
