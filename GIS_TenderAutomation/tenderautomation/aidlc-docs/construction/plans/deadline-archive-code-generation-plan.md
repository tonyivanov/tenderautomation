# Code Generation Plan - Deadline Extraction, Archive, Reconciliation, and 60% Coverage

## Plan Status

- **Project type**: Brownfield FastAPI monolith
- **Unit**: Coordinated deadline/archive change across Core, Adapters, Web, and CLI
- **Stories**: US-04, US-08, US-09
- **Approved design**: `aidlc-docs/construction/deadline-archive/functional-design/`
- **Baseline verification**: 96 tests pass; aggregate line coverage over `src/` is 37% (3995 statements, 2524 missed)
- **Execution rule**: This document is the single source of truth for Code Generation. Execute steps in order and mark each checkbox immediately after completion.

## Unit Context and Boundaries

### Responsibilities

- **Core models and deadline service** own normalized deadline contracts, deterministic parsing/selection rules, UTC normalization, expiry classification, and reconciliation counters.
- **Platform adapters** own authenticated/public transport, allowlisted canonical detail URLs, platform markup parsing, and safe external-failure classification.
- **Repository** owns deterministic candidate selection, conditional per-record updates, remaining-candidate counts, and a cross-process PostgreSQL advisory lock. No schema migration is required.
- **Reconciliation service** orchestrates bounded enrichment without importing concrete adapter implementations or changing workflow status.
- **Web** owns computed Archive presentation and authenticated admin Post-Redirect-Get interaction.
- **CLI** exposes the same reconciliation service and counters as the admin action.
- **Build configuration and tests** enforce at least 60% aggregate line coverage over all `src/` production modules without exclusions added for metric manipulation.

### Dependencies and Interfaces

- `ReconciliationService` depends only on `AdapterRegistry`, `PlatformAdapter`, and `TenderRepository`.
- `PlatformAdapter.enrich_deadline(...)` accepts an authenticated `AuthSession` plus an existing `TenderModel`, and returns a secret-safe `DeadlineExtractionOutcome`.
- Repository reconciliation updates may set a missing deadline, canonical URL, and provenance in `raw_data`; they must never overwrite a non-null deadline or change title, qualification, status, or actions.
- B2B-Center retains both configured transports (`endpoint` and `playwright`). Each transport performs its own detail fallback using its existing session/context, and merge quality determines the retained record.
- Bidzaar always constructs `https://bidzaar.com/app/process/light/{external_id}` from a validated opaque identifier and never follows an arbitrary API-provided host/path.
- Archive membership uses the shared `is_expired(deadline, now_utc)` predicate and is never persisted.

### Logical Entities

- `NormalizedDeadline`, `DeadlineCandidate`, `DeadlineExtractionOutcome`
- `ReconciliationCommand`, `ReconciliationResult`
- Existing `TenderModel`/`TenderORM`; no new table, column, enum value, or migration

## Story Traceability

| Story | Planned implementation |
|---|---|
| US-04 | Steps 2, 8: shared expiry predicate; Archive tab/count/order; expired exclusion from P1/P2; All and workflow-status preservation |
| US-08 | Steps 2, 4, 5: strict parsing, provenance, both B2B transports, Bidzaar fallback/canonical URL, no collection-time expiry deletion |
| US-09 | Steps 3, 6, 9: bounded/idempotent repository and service operation, admin action, CLI command, safe counters and overlap rejection |
| Project NFR >=60% | Steps 10 and 11: focused production-behavior tests plus blocking local/CI coverage gate |

## Generation Steps

### Step 1 - Establish executable test fixtures and contract skeletons

- [x] Add reusable test builders and dependency overrides in `tests/conftest.py` for timezone-aware tenders, authenticated users, repository doubles, and FastAPI route tests without live platform/LLM calls.
- [x] Create `src/core/models/deadline.py` with typed enums/records for normalized deadlines, extraction outcomes, commands, and results; export them from `src/core/models/__init__.py`.
- [x] Extend `src/core/adapters/base.py` with the async, platform-neutral `enrich_deadline` contract and keep `src/core/adapters/registry.py` as the only adapter lookup boundary.
- [x] Add contract tests in `tests/unit/core/test_deadline_contracts.py` and registry tests in `tests/unit/core/test_adapter_registry.py`, including bounds and secret-safe result representations.

### Step 2 - Generate shared deadline business logic with property tests

- [x] Create `src/core/services/deadlines.py` for strict supported-format parsing, platform-local date-only end-of-day semantics, UTC normalization, labelled-candidate precedence/conflict handling, provenance shaping, and `is_expired`.
- [x] Export the intended public helpers from `src/core/services/__init__.py` without leaking adapter-specific transport concerns into Core.
- [x] Create `tests/unit/core/test_deadlines.py` with example and Hypothesis properties for arbitrary input safety, timezone awareness, date-only `23:59:59`, normalization idempotence, equality boundaries, expiry monotonicity, label precedence, same-priority ambiguity, and status-independent archive membership.
- [x] Confirm malformed, impossible, unlabelled, publication, clarification, signing, and result dates remain unresolved.

### Step 3 - Add repository reconciliation operations without a migration

- [x] Modify `src/core/repositories/tender.py` to select candidates deterministically by `updated_at DESC, id`, bounded to 1..200, and count remaining candidates using the same predicate.
- [x] Add a conditional per-record update that canonicalizes Bidzaar URLs, fills only null deadlines, merges provenance into `raw_data`, recomputes the content hash when required, and commits each row independently.
- [x] Add a named PostgreSQL advisory-lock context used for reconciliation so web and CLI processes reject overlap and release the lock in `finally`; do not add a lock table or migration.
- [x] Create `tests/unit/core/test_tender_repository_reconciliation.py` covering candidate ordering/bounds, conditional writes, status/action preservation, per-record commits, remaining counts, and advisory-lock acquire/release paths with database calls mocked at the repository boundary.

### Step 4 - Strengthen B2B-Center extraction while preserving both transports

- [x] Modify `src/adapters/b2bcenter/parsers.py` to reuse shared normalization, parse supported listing formats strictly, extract only explicitly labelled detail candidates, and return provenance without guessing.
- [x] Modify `src/adapters/b2bcenter/scraper.py` so endpoint mode reuses its `httpx.AsyncClient` and cookies for bounded detail requests, while Playwright mode reuses its authenticated browser context and a single detail page; always close resources on success and failure.
- [x] Replace first-row-wins deduplication with deterministic field merging: valid structured deadline over valid detail deadline, valid over null, and non-empty ancillary fields only filling gaps.
- [x] Modify `src/adapters/b2bcenter/adapter.py` to persist normalized deadline/provenance and implement `enrich_deadline` for reconciliation through the platform boundary.
- [x] Extend `tests/unit/adapters/b2bcenter/test_parsers.py`, `test_scraper_modes.py`, and `test_adapter.py` for endpoint and Playwright fallback, priority conflicts, merge quality, 404/timeout/CAPTCHA safe outcomes, cookie/context reuse, and cleanup.

### Step 5 - Correct Bidzaar collection, URL normalization, and detail fallback

- [x] Modify `src/adapters/bidzaar/api_client.py` to retain fetched tenders with expired deadlines, keep incremental publication filtering, and expose strict structured deadline extraction with `api` provenance.
- [x] Modify `src/adapters/bidzaar/adapter.py` to derive and validate the opaque external ID, always construct the canonical allowlisted URL, enrich a missing/invalid deadline from that URL with bounded transport, and implement the common `enrich_deadline` contract.
- [x] Ensure 404, unauthorized, timeout, invalid markup, and network failures preserve the tender with a null deadline and a safe category; never log response bodies, credentials, cookies, tokens, or untrusted URL query strings.
- [x] Extend `tests/unit/adapters/bidzaar/test_integrator_api.py`, `test_adapter.py`, and `tests/unit/adapters/test_bidzaar_incremental.py` for expired-row retention, canonicalization idempotence, malicious-link rejection by construction, detail precedence, and safe failure behavior.

### Step 6 - Generate the shared reconciliation service

- [x] Create `src/core/services/reconciliation.py` to validate `ReconciliationCommand`, acquire the repository advisory lock, authenticate each needed registered adapter once, process at most the requested batch, and aggregate only approved counters.
- [x] Preserve each tender on unresolved/external failure, isolate per-row failures, never overwrite a non-null deadline, and calculate `remaining_candidates` after successful/partial runs.
- [x] Export `ReconciliationService` from `src/core/services/__init__.py` and centralize application wiring so web and CLI construct the same registry/repository/service graph rather than duplicate behavior.
- [x] Create `tests/unit/core/test_reconciliation.py` with examples and Hypothesis properties for bounds, idempotent reruns, partial success, deadline/status preservation, one authentication per platform, safe failures, and `already_running` with zero processed rows.

### Step 7 - Consolidate application composition

- [x] Create `src/core/bootstrap.py` (or the smallest equivalent existing-location factory) for shared adapter registry, pipeline, and reconciliation construction.
- [x] Modify `src/core/cli.py` and `src/web/routers/admin_router.py` to use the shared factories, preserving Telegram registration only for the CLI pipeline path and preserving existing admin collection behavior.
- [x] Add focused tests in `tests/unit/core/test_bootstrap.py` to prove both adapters are registered once and no live authentication/network call occurs during construction.

### Step 8 - Implement computed Archive behavior in the tender list

- [x] Modify `src/web/routers/tenders_router.py` to use `is_expired`, apply platform and text filters before all tab counts, exclude expired tenders from P1/P2, include every expired tender in Archive, keep unknown deadlines in their queue, and preserve All/status behavior.
- [x] Sort Archive by deadline descending then stable tender ID; keep active ordering deterministic and calculate counts before pagination.
- [x] Modify `src/web/templates/tenders/list.html` to render the Archive badge and stable `data-testid="tenders-tab-{tab}"` selectors for every tab without changing tender status.
- [x] Create `tests/unit/web/test_tenders_archive.py` for P1/P2/Archive/All membership, unknown deadlines, count/filter ordering, tie-breaking, status independence, pagination, authentication, and template selectors.

### Step 9 - Expose reconciliation through admin and CLI

- [x] Modify `src/web/routers/admin_router.py` with an admin-only POST endpoint, strict integer/default/range validation, authoritative overlap handling, safe aggregate result state, and Post-Redirect-Get.
- [x] Modify `src/web/templates/admin/panel.html` with the accessible batch form and stable selectors `deadline-reconcile-form`, `deadline-reconcile-batch-size`, `deadline-reconcile-submit`, and `deadline-reconcile-result`.
- [x] Modify `src/core/cli.py` with `reconcile-deadlines --batch-size` using Click range validation and the same async service/result counters; return nonzero only for command/operational failure, not unresolved rows.
- [x] Create `tests/unit/web/test_admin_reconciliation.py` and `tests/unit/core/test_cli.py` for admin authorization, invalid input before external calls, PRG, safe rendering, CLI parity, partial results, and overlap.

### Step 10 - Raise production-code coverage to at least 60%

- [x] Use the coverage report after Steps 1-9 to calculate the remaining line deficit; do not omit, pragma-exclude, or relocate production code merely to increase the percentage.
- [x] Add focused behavior tests for currently uncovered pure/business paths in `tests/unit/core/test_scoring_v2_gates.py` and `tests/unit/core/test_scoring_v2_pipeline.py`.
- [x] Add focused behavior tests for orchestration and aggregation paths in `tests/unit/core/test_scoring_v3_aggregator.py`, `test_scoring_v3_post_filter.py`, `test_scoring_v3_pipeline.py`, and `test_scoring_v3_deep_analyzer.py`, mocking LLM transports and secrets.
- [x] Extend repository, collection, admin, tenders, CLI, notification, and export tests only as indicated by the fresh report, prioritizing stable externally visible behavior over line-by-line implementation coupling.
- [x] Iterate until `python -m pytest --hypothesis-seed=20260717 --cov=src --cov-report=term-missing --cov-fail-under=60` passes with aggregate line coverage >=60%.

### Step 11 - Make 60% a permanent local and GitLab gate

- [x] Modify `pyproject.toml` with a coverage report threshold of 60 while retaining `source = ["src"]` and the existing non-production omissions only.
- [x] Modify `.gitlab-ci.yml` so `test:unit` explicitly runs with `--cov-fail-under=60` and still uploads `coverage.xml` even when the threshold fails.
- [x] Update `README.md` with Archive behavior, strict/fallback deadline semantics, admin and CLI reconciliation usage, default/max batch sizes, no-live-call unit-test behavior, and the exact local 60% coverage command.
- [x] Add/extend configuration contract tests in `tests/unit/web/test_merge_readiness.py` to prevent accidental removal or weakening of the threshold.

### Step 12 - Complete Code Generation evidence and targeted verification

- [x] Run formatter/static syntax checks used by the repository and all targeted tests added in Steps 1-11; fix generation defects before review.
- [x] Run `git diff --check`, inspect the complete diff for secrets and unrelated user changes, and verify no duplicate brownfield files or database migration were introduced.
- [x] Run `graphify update .` exactly once after the final codebase change and use the refreshed graph to verify Core -> Adapter -> Web dependency direction.
- [x] Create `aidlc-docs/construction/deadline-archive/code/implementation-summary.md` with modified/created files, story/rule traceability, security/PBT evidence, test-generation evidence, and any Build-and-Test prerequisites.
- [x] Mark all completed steps and story mappings in this plan, update `aidlc-docs/aidlc-state.md`, log the Code Generation review prompt in `aidlc-docs/audit.md`, and stop for explicit approval before Build and Test.

## Security Baseline Controls

- Canonical platform allowlists are constructed internally; admin/CLI accept no URL or tender-ID list.
- Batch input is validated before external calls and capped at 200.
- Server-side admin role checks remain authoritative.
- External errors are reduced to approved safe categories.
- Tests assert that logs/results do not expose credentials, cookies, tokens, response bodies, or arbitrary URLs.
- PostgreSQL advisory locking prevents duplicate traffic across web and CLI processes without adding persisted lock state.

## Property-Based Testing Controls

- Arbitrary parser text never raises.
- Date-only normalization, UTC normalization, canonical URL normalization, expiry monotonicity, merge quality, batch bounds, and reconciliation reruns satisfy the approved invariants.
- Deterministic examples remain mandatory for known platform markup and all failure categories.

## Explicit Non-Goals

- No `ARCHIVED`/`archive` value in `TenderStatus`.
- No database schema migration.
- No removal of B2B-Center endpoint or Playwright collection mode.
- No live platform, Telegram, or LLM call in unit/property tests.
- No production-module coverage exclusion added to reach 60%.
- No deployment topology change; only CI quality-gate configuration changes.

## Completion Gate

Code Generation may begin only after explicit approval of this entire plan. Formal full-suite, strict mypy, Bandit, dependency audit, Docker build, and smoke verification remain the subsequent Build and Test stage, although targeted tests run during generation.
