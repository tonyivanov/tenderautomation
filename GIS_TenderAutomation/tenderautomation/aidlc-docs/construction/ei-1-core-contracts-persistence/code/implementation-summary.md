# EI-1 Core Contracts & Persistence — Implementation Summary

## Outcome

EI-1 now provides typed export-readiness contracts, additive procedure-state
persistence, pure eligibility/freshness/archive decisions, monotonic per-tender
inspection application, a read-only V3 SQLite projection, a fail-closed adapter
inspection boundary, and bounded asynchronous readiness orchestration.

Workflow `TenderStatus` remains independent from source procedure state. Ordinary
collection upserts do not overwrite procedure inspection metadata. Concrete
Bidzaar and B2B-Center inspection implementations and the Web ZIP route remain
assigned to EI-2 and EI-3 respectively; both B2B-Center endpoint and Playwright
modes remain intact.

## Created application and test artifacts

- `src/core/models/export.py`
- `src/core/services/export_decisions.py`
- `src/core/services/v3_export.py`
- `src/core/services/export_readiness.py`
- `migrations/versions/0003_export_integrity.py`
- `tests/strategies/export_integrity.py`
- EI-1 contract, policy, repository, projection, readiness, stateful and guarded
  persistence tests under `tests/unit/core/` and `tests/integration/`.

Existing Core model, ORM, repository, adapter, credential resolver, service export
and bootstrap files were modified in place. No duplicate brownfield files or new
runtime dependency were introduced.

## Behavioral evidence

- Procedure state values: unknown, active, closed, completed, cancelled and
  not_found.
- Freshness boundary: less than 24 hours is fresh; 24 hours is stale.
- Verified non-null enrichment can overwrite source fields; null never erases.
- Newer verified inspection can reopen a previously inactive procedure.
- Explicit IDs retain request order; bulk selection unions legacy-qualified and
  V3 P1/P2 references before the 50-item cap.
- Missing/corrupt V3 cache is distinct from a not-found classification. A legacy
  filtered tender fails closed without spending platform network budget.
- Authentication and inspection are bounded to 30 seconds, aggregate preparation
  to 120 seconds, external concurrency to four, with no retries.

## Verification performed during generation

- Targeted pytest with Hypothesis seed `20260717`: 56 passed, 1 guarded
  PostgreSQL integration test skipped because `TEST_POSTGRESQL_URL` was absent.
- Strict mypy: success for 11 modified/new Core modules.
- Alembic `0002:0003` offline SQL generated successfully.
- `git diff --check`: clean.
- Coverage gate remains `fail_under = 60` in `pyproject.toml`.
- Graphify graph refreshed after each implementation batch.

Real PostgreSQL upgrade/downgrade and concurrent transaction scenarios remain a
guarded Build & Test prerequisite; no localhost or live platform call was made.

## Extension compliance

Security Baseline applicable controls are satisfied by bounded validated DTOs,
parameterized SQLite reads, safe error categories, fail-closed external handling,
resource closure and secret-free structured aggregate logging. Infrastructure,
HTTP-header, IAM and topology controls are unchanged or not applicable to EI-1.

PBT uses reusable domain strategies, example regressions, invariant/oracle/
idempotency/state-sequence properties, normal Hypothesis shrinking and the fixed
CI seed. Serialization ZIP round-trip remains EI-3 scope.
