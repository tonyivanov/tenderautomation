# EI-1 Code Generation Plan — Core Contracts & Persistence

## Plan status

- **Project type**: Brownfield FastAPI monolith, Python 3.12 production runtime.
- **Unit**: EI-1 Core Contracts & Persistence.
- **Workspace code root**: repository root; application files remain under
  `src/`, `migrations/` and `tests/`, never under `aidlc-docs/`.
- **Approved design**:
  `aidlc-docs/construction/ei-1-core-contracts-persistence/`.
- **Execution rule**: This document is the single source of truth for EI-1 Code
  Generation. Execute steps in order and mark each checkbox immediately.

## Part 1 planning checklist

- [x] Load EI-1 Functional Design, NFR Requirements and NFR Design.
- [x] Load requirements, Application Design, unit dependencies and story map.
- [x] Inspect existing Core models, ORM, migrations, repository, adapter ABC,
  bootstrap, V3 SQLite readers and tests through source and Graphify.
- [x] Confirm EI-1 prerequisites and dependency direction `EI-1 → EI-2 → EI-3`.
- [x] Define exact brownfield paths and ordered implementation steps.
- [x] Map Security Baseline and PBT-01–PBT-10 into the plan.
- [x] Receive explicit approval of this complete generation plan.

## Unit context and boundaries

### Responsibilities

- Core owns normalized procedure/export contracts, pure eligibility/TTL/archive
  decisions and the async readiness orchestration boundary.
- PostgreSQL owns durable procedure state, successful/attempt timestamps, source
  and safe error category through additive columns on `tenders`.
- `TenderRepository` owns stable candidate reads and atomic monotonic result
  application; it never interprets HTTP or CAPTCHA.
- `V3ExportProjection` owns read-only final V3 judge/queue resolution from the
  existing SQLite cache and distinguishes found/not-found/unavailable.
- `PlatformAdapter` exposes a non-breaking async `inspect_tender` contract. EI-2
  will provide both concrete implementations; the EI-1 default fails closed.
- `ExportReadinessService` coordinates abstractions without FastAPI, Jinja2, ZIP,
  LLM clients or concrete adapter imports.

### Explicit non-goals for EI-1

- No concrete B2B-Center/Bidzaar inspection parsing; that is EI-2.
- No export router, JSONL, prompt, manifest, ZIP, template or Docker change; that
  is EI-3.
- No changes to Telegram, email or LLM scoring pipelines.
- No new runtime dependency, queue, cache service or deployment topology.
- No removal of B2B-Center endpoint or Playwright mode.
- No live platform, LLM, Telegram or SMTP calls in generated tests.

## Requirement and acceptance traceability

| Requirement | EI-1 implementation steps |
|---|---|
| FR-03 Classification context/eligibility | Steps 1, 3, 5, 7 |
| FR-04 Live enrichment core contract/persistence | Steps 1, 2, 4, 6, 7 |
| FR-05 Activity/archive/failure decisions | Steps 1, 3, 4, 7 |
| FR-06 Single/bulk preparation outcomes | Steps 3, 4, 5, 7 |
| FR-07 Procedure/V3/completeness DTOs | Steps 1, 5, 7 |
| NFR-01 Bounded calls | Step 7 |
| NFR-02 Security/fail closed | Steps 1–8 |
| NFR-03 Observability | Step 7 |
| NFR-04 Compatibility | Steps 1, 2, 6 |
| NFR-05 Quality and coverage | Steps 3–5, 7, 9, 10 |
| AC-04 filtered + V3 P2 support | Steps 3, 5, 7 |
| AC-05 completeness support | Steps 1, 7 |
| AC-06 archive result | Steps 2–4, 7 |
| AC-07 external failure safety | Steps 1, 6, 7 |
| AC-08 bulk verified-only preparation | Steps 3–5, 7 |
| AC-10 tests/security/coverage support | Steps 9–10 |

The current iteration skipped new User Stories because requirements and ACs were
already explicit. Existing US-03 Core/export-contract responsibility is advanced
by Steps 1, 5 and 7; traceability remains requirements-first.

## Owned entities and interfaces

- `ProcedureState`, `InspectionSource`, `InspectionErrorCategory`.
- `TenderInspectionResult`, `InspectionApplyResult`.
- `V3ExportContext`, `V3LookupResult`.
- `ExportRequest`, `PreparedTender`, `ExportOutcome`,
  `ExportPreparationResult` and summary DTO.
- `PlatformAdapter.inspect_tender(...)`.
- `TenderRepository.get_export_candidates(...)` and `apply_inspection(...)`.
- `V3ExportProjection.get_many(...)`.
- `ExportReadinessService.prepare(...)`.

## Generation steps

### Step 1 — Generate export/procedure domain contracts

- [x] Create `src/core/models/export.py` with string enums and immutable typed
  DTOs for procedure state, inspection source/error, V3 lookup/context, request,
  apply result and five-category preparation result.
- [x] Enforce timezone-aware timestamps, batch maximum 50, stable ID
  deduplication, verified/error consistency and bounded provenance: scalar-only
  allowlist, at most 16 keys and at most 8 KiB canonical UTF-8 JSON.
- [x] Modify `src/core/models/tender.py` to add procedure fields with safe defaults
  while preserving the independent `TenderStatus` state machine and existing
  JSONL fields.
- [x] Modify `src/core/models/__init__.py` to export only the intended public
  contracts without importing Web or adapter implementations.
- [x] Extend `tests/conftest.py` with reusable timezone-aware procedure/export
  builders, avoiding credentials or live transports.
- [x] Create `tests/unit/core/test_export_contracts.py` with example tests for
  defaults, validation boundaries, safe representation and model dump/validate
  compatibility.

### Step 2 — Add the backward-compatible persistence schema

- [x] Create `migrations/versions/0003_export_integrity.py`, revising `0002`, to
  add `procedure_state` with server default `unknown`, nullable successful/attempt
  timestamps, nullable source/error columns and an index useful for state reads.
- [x] Keep the migration additive so the previous image can read/write `tenders`;
  implement downgrade by dropping only the new index/columns in reverse order.
- [x] Modify `src/core/orm/tender.py` with matching SQLAlchemy mappings and
  timezone-aware columns.
- [x] Modify `TenderRepository.orm_to_model` and insert mapping so new rows and
  legacy/default rows round-trip without overwriting procedure metadata during
  ordinary collection upserts.
- [x] Create `tests/unit/core/test_export_migration.py` for revision chain,
  column/default/index operations, downgrade order and ORM/model mapping.
- [x] Create `tests/integration/test_export_persistence.py` with an explicit
  PostgreSQL test-environment guard for real upgrade/read/write verification in
  Build & Test; default no-DB unit runs must not contact localhost.

### Step 3 — Generate pure readiness decision policy and PBT strategies

- [x] Create `src/core/services/export_decisions.py` with pure injectable-clock
  helpers for classification eligibility, 24-hour freshness, inspection need,
  archive predicate, verified non-null merge, completeness warnings and stable
  five-way partition validation.
- [x] Preserve exact boundaries: `<24h` fresh, `>=24h` stale; expired/inactive is
  archive; `unknown` is unverified; budget absence is not a warning; workflow
  status never changes these decisions.
- [x] Create reusable Hypothesis strategies in
  `tests/strategies/export_integrity.py` and package exports in
  `tests/strategies/__init__.py` for tenders, aware timestamps, inspection
  results, provenance and state command sequences.
- [x] Create `tests/unit/core/test_export_decisions.py` for explicit regression
  examples corresponding to BR-01–BR-19.
- [x] Create `tests/unit/core/test_export_decisions_properties.py` for TP-01–TP-09:
  archive/status invariance, inactive/unknown, TTL boundary, null-preserving
  merge, idempotency, failure safety, eligibility oracle, partition conservation
  and reopening sequences.

### Step 4 — Implement candidate reads and atomic monotonic persistence

- [x] Modify `src/core/repositories/tender.py` with a strict 1..50 export limit,
  explicit-ID lookup preserving request order, deterministic bulk reads and
  helpers needed to union legacy-qualified with V3 P1/P2 references before the
  final cap.
- [x] Implement one-transaction-per-tender `apply_inspection`: row lock only
  during merge, allowlisted non-null enrichment, independent workflow status,
  content hash/update timestamp only on business change and detached return DTO.
- [x] Apply verified results monotonically by `attempted_at`; support applied,
  idempotent, stale, equal-timestamp conflict and missing outcomes. Failure may
  update only newer attempt/error metadata and never verified state.
- [x] Use rollback and safe repository exceptions/categories; never expose SQL,
  exception messages, raw payloads or arbitrary provenance keys.
- [x] Create `tests/unit/core/test_tender_repository_export.py` for query bounds
  and ordering, each apply outcome, null preservation, content-hash idempotency,
  status/qualification preservation, per-record rollback and safe errors.
- [x] Extend the guarded PostgreSQL integration test with concurrent old/new
  result ordering and per-tender transaction isolation scenarios.

### Step 5 — Generate the read-only V3 export projection

- [x] Create `src/core/services/v3_export.py` with a configurable SQLite path,
  parameterized batch reads, stable ID preference, exact-unambiguous title
  fallback and one short-lived connection per worker call.
- [x] Centralize existing judge override and queue calculation, including the
  confidence threshold, while keeping legacy Web readers unchanged until EI-3.
- [x] Return typed `found`, `not_found` and `unavailable` results; do not collapse
  missing/corrupt/locked cache into false classification absence.
- [x] Provide the V3 P1/P2 candidate references required for bulk union without
  importing PostgreSQL, Web modules or LLM clients.
- [x] Create `tests/unit/core/test_v3_export.py` using temporary SQLite databases
  for current/legacy schemas, judge override, queue parity, ID/title matching,
  duplicates, deterministic ordering, unavailable/corrupt/lock timeout and
  connection cleanup.
- [x] Add an eligibility oracle property comparing projection queue outcomes with
  the simple BR-01 model across generated V3/legacy combinations.

### Step 6 — Extend the adapter contract without concrete platform work

- [x] Modify `src/core/adapters/base.py` with async `inspect_tender(...)` returning
  `TenderInspectionResult`; use a safe default `unknown/unverified` result so
  existing adapters remain instantiable until EI-2.
- [x] Refactor the existing platform credential resolver in
  `src/core/services/collection.py` into a reusable public Core callable and
  update `src/core/services/reconciliation.py` without changing credential
  storage, logging or collection behavior.
- [x] Keep credentials outside request/result DTOs and inject the resolver/session
  dependency into readiness orchestration; unknown platform fails closed.
- [x] Extend `tests/unit/core/test_adapter_registry.py` and existing collection/
  reconciliation tests for the new default contract and credential refactor.
- [x] Assert no result/log representation contains usernames, passwords, tokens,
  cookies or response bodies.

### Step 7 — Generate bounded async `ExportReadinessService`

- [x] Create `src/core/services/export_readiness.py` with request-scoped
  `BlockingIOBridge`, one-session-per-platform scope, shared external semaphore
  of four, separate bounded worker-I/O bridge and absolute 120-second deadline.
- [x] Enforce a 30-second maximum per authentication/inspection, no retries,
  cleanup reserve, cooperative task cancellation, session cleanup and no
  detached/background tasks after completion.
- [x] Compose repository candidates, V3 tri-state eligibility, cached/archive
  decisions, fake/concrete adapter contract calls, validation, atomic apply and
  stable five-category result partition.
- [x] Apply approved V3-unavailable behavior: legacy qualified continues with
  unavailable context; legacy filtered becomes unverified, never false
  ineligible and never consumes platform network budget.
- [x] Emit safe candidate events and one request aggregate through the existing
  structured logger with counts/durations/categories but no title, description,
  credentials, provenance payload or exception message.
- [x] Create `tests/unit/core/test_export_readiness.py` with fake repository,
  projection, adapters and sessions for cached/single/bulk paths, partial success,
  concurrency ≤4, 30/120 timeouts, no retry, cancellation cleanup, stable order,
  V3 failure, contract/DB errors and event-loop responsiveness during sync I/O.
- [x] Create `tests/unit/core/test_export_readiness_stateful.py` with a Hypothesis
  model/state machine for verified/failure/stale/conflict sequences and a
  sequential oracle for concurrent preparation results.

### Step 8 — Wire public Core exports and composition

- [x] Modify `src/core/services/__init__.py` to export the intended decision,
  projection and readiness public surfaces without Web imports.
- [x] Modify `src/core/bootstrap.py` with a `build_export_readiness_service`
  factory that wires registry, repository, V3 projection and injected credential
  resolver but performs no authentication/network/database work at construction.
- [x] Extend `tests/unit/core/test_bootstrap.py` to prove construction registers
  each adapter once, does not authenticate, does not open SQLite/PostgreSQL and
  exposes no concrete adapter dependency from Core service modules.
- [x] Verify the existing collection, reconciliation, CLI and web import paths
  remain compatible; do not connect the Web export route until EI-3.

### Step 9 — Generate integration and quality evidence

- [x] Ensure every critical BR/AC owned by EI-1 has at least one deterministic
  example test in addition to property coverage.
- [x] Ensure PBT shrinking stays enabled and use the existing reproducible CI seed
  `20260717`; add every discovered minimal counterexample as an example regression.
- [x] Run the EI-1 targeted pytest set with the fixed seed and no live external
  calls, then fix all generation defects.
- [x] Run strict mypy on all modified/new Core modules and targeted tests where
  configured; fix types without broad ignores.
- [x] Compile/import the `0003` migration and generate offline Alembic SQL; leave
  real PostgreSQL upgrade/downgrade execution to the guarded integration gate in
  Build & Test.
- [x] Confirm the aggregate project coverage configuration remains at least 60%
  and no production exclusion/pragma was added to manipulate the metric.

### Step 10 — Finalize EI-1 generation evidence

- [x] Run `git diff --check`, inspect the complete EI-1 diff for secrets and
  unrelated user changes, and verify no duplicate brownfield files were created.
- [x] Run `graphify update .` exactly after the final codebase change and verify
  Core does not import FastAPI/Jinja2/concrete adapters/LLM clients.
- [x] Create
  `aidlc-docs/construction/ei-1-core-contracts-persistence/code/implementation-summary.md`
  with created/modified files, requirements/rules, migration, Security/PBT and
  targeted-test evidence plus Build & Test prerequisites.
- [x] Mark every completed generation checkbox and traceability item, update
  `aidlc-docs/aidlc-state.md`, log the Code Generation review prompt and stop for
  explicit approval before entering EI-2.

## Security Baseline planning compliance

| Rule | Status in EI-1 plan | Planned control |
|---|---|---|
| SECURITY-01 | Unchanged | Existing PostgreSQL/SQLite; no new store or transport |
| SECURITY-02 | N/A | No network intermediary |
| SECURITY-03 | Applicable | Structured safe candidate/request events |
| SECURITY-04 | N/A | No HTML endpoint in EI-1 |
| SECURITY-05 | Applicable | Typed/bounded IDs, DTOs, provenance and parameterized SQL |
| SECURITY-06 | N/A | No IAM change |
| SECURITY-07 | N/A | No network topology change |
| SECURITY-08 | N/A for Core | Authenticated object access belongs to EI-3 route |
| SECURITY-09 | Applicable | Safe error categories without internals |
| SECURITY-10 | Unchanged | No dependencies; existing pins/scans/SBOM retained |
| SECURITY-11 | Applicable | Batch/concurrency/deadline and misuse tests |
| SECURITY-12 | Applicable | Injected credentials, no secrets in DTO/logs/tests |
| SECURITY-13 | Applicable | Typed deserialization, monotonic/auditable writes |
| SECURITY-14 | Unchanged | Existing central controls plus bounded aggregate events |
| SECURITY-15 | Applicable | Explicit failures, rollback, cancellation and cleanup |

No blocking Security finding exists in the plan.

## Property-Based Testing planning compliance

| Rule | Status in EI-1 plan | Planned evidence |
|---|---|---|
| PBT-01 | Applicable | TP-01–TP-09 mapped in Step 3 |
| PBT-02 | N/A for EI-1 export format | JSONL/ZIP round-trip belongs to EI-3; DTO dump/validate has examples |
| PBT-03 | Applicable | State, TTL, archive, failure and partition invariants |
| PBT-04 | Applicable | Merge/dedup idempotency properties |
| PBT-05 | Applicable | Eligibility, concurrent apply and preparation oracles |
| PBT-06 | Applicable | Stateful verified/failure/stale/conflict model |
| PBT-07 | Applicable | Reusable constrained strategies under `tests/strategies/` |
| PBT-08 | Applicable | Shrinking plus fixed/logged seed `20260717` |
| PBT-09 | Applicable | Existing Hypothesis dependency and pytest integration |
| PBT-10 | Applicable | Example regressions accompany every critical property path |

No blocking PBT finding exists in the plan.

## Expected file scope

### Create

- `src/core/models/export.py`
- `src/core/services/export_decisions.py`
- `src/core/services/v3_export.py`
- `src/core/services/export_readiness.py`
- `migrations/versions/0003_export_integrity.py`
- `tests/strategies/__init__.py`
- `tests/strategies/export_integrity.py`
- `tests/unit/core/test_export_contracts.py`
- `tests/unit/core/test_export_migration.py`
- `tests/unit/core/test_export_decisions.py`
- `tests/unit/core/test_export_decisions_properties.py`
- `tests/unit/core/test_tender_repository_export.py`
- `tests/unit/core/test_v3_export.py`
- `tests/unit/core/test_export_readiness.py`
- `tests/unit/core/test_export_readiness_stateful.py`
- `tests/integration/test_export_persistence.py`
- `aidlc-docs/construction/ei-1-core-contracts-persistence/code/implementation-summary.md`

### Modify in place

- `src/core/models/tender.py`
- `src/core/models/__init__.py`
- `src/core/orm/tender.py`
- `src/core/repositories/tender.py`
- `src/core/adapters/base.py`
- `src/core/services/collection.py`
- `src/core/services/reconciliation.py`
- `src/core/services/__init__.py`
- `src/core/bootstrap.py`
- `tests/conftest.py`
- `tests/unit/core/test_adapter_registry.py`
- `tests/unit/core/test_bootstrap.py`
- affected collection/reconciliation regression tests if the public credential
  resolver rename requires it.

### Explicitly untouched in EI-1

- `src/adapters/` concrete implementations.
- `src/web/`, templates and export routes.
- `prompts/`, `Dockerfile`, Compose and GitLab CI.
- LLM scoring clients/pipelines and notification modules.

## Completion gate

Code Generation Part 2 may begin only after explicit approval of this entire
plan. Full suite, real migration integration, Bandit, dependency audit, Docker,
SBOM and smoke remain mandatory in the later Build & Test stage.
