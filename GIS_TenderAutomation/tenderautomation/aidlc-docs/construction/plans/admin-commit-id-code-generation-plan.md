# Code Generation Plan - Admin Commit ID

This plan is the single source of truth for implementing the approved commit ID display
change. Application and deployment files remain in the workspace root; AI-DLC summaries
remain under `aidlc-docs/`.

## Unit Context

- **Unit**: Existing Web Application and production build metadata.
- **Requirement references**: FR-COMMIT-01 through FR-COMMIT-04 and
  NFR-COMMIT-01 through NFR-COMMIT-04.
- **User stories**: N/A; skipped for this focused change.
- **Database entities**: None.
- **External service contracts**: None.
- **Dependencies**: GitLab predefined `CI_COMMIT_SHA`, Docker build arguments,
  Pydantic Settings, FastAPI/Jinja template context.

## Expected Interfaces

- Build argument: `APP_COMMIT_SHA`.
- Runtime environment variable: `APP_COMMIT_SHA`.
- Settings field: `app_commit_sha: str` with default `unknown`.
- Admin template context key: `commit_id`.
- UI selector: `data-testid="admin-commit-id"`.

## Generation Steps

### Step 1: Runtime configuration and normalization

- [x] Add `app_commit_sha` to `src/core/config.py` with a safe default.
- [x] Add a deterministic helper in `src/web/routers/admin_router.py` that returns the
  first eight hexadecimal characters or `unknown` for missing/malformed input.
- [x] Pass the normalized `commit_id` in the `/admin` template context only.
- [x] Add focused example-based tests for valid, missing, short, whitespace, and
  non-hexadecimal values.

### Step 2: Admin top-bar rendering

- [x] Update `src/web/templates/base.html` to render the commit label only when
  `commit_id` is defined.
- [x] Add the stable selector `data-testid="admin-commit-id"`.
- [x] Keep existing authenticated navigation, username, and logout behavior unchanged.
- [x] Add a Jinja rendering regression test proving the admin label is present and an
  ordinary page without the context key does not display it.

### Step 3: Production image metadata

- [x] Add `ARG APP_COMMIT_SHA=unknown` and the corresponding runtime `ENV` to `Dockerfile`.
- [x] Update `.gitlab-ci.yml` so `build:image` passes `CI_COMMIT_SHA` through
  `--build-arg APP_COMMIT_SHA`.
- [x] Extend the deployment contract test to pin both sides of this build-time contract.

### Step 4: Production smoke coverage

- [x] Extend `scripts/smoke_check.py` to request `/admin` with the authenticated admin
  session and assert the commit label exists.
- [x] Preserve the existing isolated PostgreSQL, authentication, Chromium, and security
  header checks.

### Step 5: Implementation documentation

- [x] Create `aidlc-docs/construction/web/code/admin-commit-id-summary.md` describing
  modified files, runtime contract, fallback behavior, and security/PBT applicability.
- [x] Refresh the repository knowledge graph after the codebase changes.
- [x] Update this plan's completed checkboxes immediately after every implementation step.
- [x] Update `aidlc-docs/aidlc-state.md` when generation is complete.

### Step 6: Build and test handoff

- [x] Run focused tests for the new behavior.
- [x] Prepare the complete change for the Build and Test stage without committing or
  pushing unless separately requested.

## Testable Properties Assessment

No PBT properties are identified for this unit. The helper is a small input-validation
boundary with a finite, explicit contract that is better documented by parameterized
examples. No round trip, state machine, business invariant, idempotent operation, or
reference algorithm is introduced.

## Security Requirements

- Render only the normalized short hexadecimal SHA or the literal `unknown`.
- Do not log or display other environment variables.
- Preserve server-side admin authorization.
- Do not execute Git or read `.git` during a request.
- Rely on Jinja autoescaping and a fixed label structure.

## Completion Criteria

- [x] All implementation steps are checked.
- [x] No duplicate brownfield files are created.
- [x] Focused tests pass (`12 passed`).
- [x] Security compliance has no blocking findings.
- [x] PBT rules are marked N/A with rationale.
- [x] Unit is ready for the Build and Test stage.
