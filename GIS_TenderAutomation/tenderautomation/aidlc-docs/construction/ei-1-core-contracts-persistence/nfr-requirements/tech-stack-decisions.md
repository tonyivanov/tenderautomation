# EI-1 Tech Stack Decisions

## Decision summary

EI-1 использует существующий production stack. Новые runtime dependencies и
отдельные сервисы не требуются.

## Runtime and async orchestration

| Decision | Choice | Rationale |
|---|---|---|
| Language/runtime | Python 3.12 | Existing supported production runtime |
| Concurrency | `asyncio.Semaphore(4)` | Standard library, request-scoped bound |
| Per-operation timeout | `asyncio.timeout(30)` or equivalent | Enforces contract around adapter awaitable |
| Batch deadline | outer `asyncio.timeout(120)` | Deterministic upper bound for request work |
| Retry | none in readiness request | Prevents doubled latency and platform load |
| Clock | injectable UTC callable | Deterministic TTL/deadline tests |

Task cancellation должна собираться через structured async orchestration;
незавершённые tasks преобразуются в safe unverified outcomes, а resources
освобождаются adapter context managers.

## Domain validation

| Decision | Choice | Rationale |
|---|---|---|
| DTO framework | Existing Pydantic v2 | Typed constraints and project consistency |
| State types | `str` enums | DB/JSON compatibility and explicit allowlist |
| Immutable results | frozen Pydantic/dataclass semantics | Prevents mutation between adapter and repository |
| Batch max | constrained integer, maximum 50 | Defense in depth |

## Persistence

| Decision | Choice | Rationale |
|---|---|---|
| Primary DB | Existing PostgreSQL | Transactional source of truth |
| ORM | Existing SQLAlchemy 2.x | Typed mappings and parameterized updates |
| Migration | Existing Alembic | Additive, versioned schema evolution |
| Transaction | one session/transaction per tender result | Partial batch progress and isolation |
| Merge | explicit column assignments | Prevents mass assignment from raw payload |

`procedure_state` получает database-compatible default `unknown`. Timestamp
columns timezone-aware. `raw_data` обновляется только bounded provenance keys.

## V3 projection

| Decision | Choice | Rationale |
|---|---|---|
| Storage | Existing SQLite V3 cache | Approved scope avoids migration to PostgreSQL |
| Access | Existing `sqlite3` with parameterized reads | No new dependency |
| Boundary | Read-only `V3ExportProjection` | One judge/queue implementation for UI/export |
| Concurrency | Short-lived read connection/current locking pattern | Avoid shared mutable cursor state |

## Logging and observability

| Decision | Choice | Rationale |
|---|---|---|
| Logging | Existing structured project logger | SECURITY-03 consistency |
| Correlation | Existing request/log context where available | Trace one export without sensitive payload |
| Metrics | Structured aggregate events | No new monitoring dependency in scope |

## Testing

| Decision | Choice | Rationale |
|---|---|---|
| Unit/integration | Existing pytest | Project standard |
| Property testing | Existing Hypothesis | PBT-09, shrinking and seed support |
| DB integration | Existing PostgreSQL Compose/test setup | Validates real migration/transactions |
| Types | Existing mypy configuration | Public Core contract gate |
| Coverage | Existing pytest-cov, minimum 60% project line coverage | Approved quality requirement |

Reusable Hypothesis strategies размещаются в existing test utilities/fixtures,
а не копируются по отдельным test modules.

## Security and supply chain

- Новые libraries не добавляются.
- Existing exact dependency pins, pip-audit, Bandit, Gitleaks, SBOM и pinned
  Docker/CI tools остаются обязательными.
- Core не получает direct access к environment credentials.

## Rejected alternatives

| Alternative | Reason rejected |
|---|---|
| Celery/Redis/background queue | Новая infrastructure topology, вне scope |
| AnyIO-specific limiter | Новый abstraction/dependency не нужен для Python 3.12 flow |
| Retrying library | Retry запрещён утверждённой policy |
| One transaction for whole batch | Теряет partial success и увеличивает lock duration |
| V3 migration to PostgreSQL | Явно отклонено в Application Design |
| Unbounded `asyncio.gather` | Нарушает capacity/security requirements |
