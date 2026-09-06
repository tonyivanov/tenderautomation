# Build and Test Summary — AI Export Integrity EI-1

## Build Status

- **Source under test**: working tree based on
  `3b7ab4463f9fee3409ca7a87bee58e960150999d` plus the documented EI-1 changes.
- **Compose validation**: passed with synthetic values and `/dev/null` env file.
- **Production image**: `tenderautomation:ei1-local`.
- **Image ID**:
  `sha256:98fac2377fecd60b801d6d65df6e5d957fa23a5723af4ef356aabba77ca016a7`.
- **Image size**: 521,979,925 bytes.
- **SBOM**: CycloneDX 1.4, 352 components, valid JSON.
- **Build status**: Success.

## Test Execution Summary

### Unit and Property Tests

- **Passed**: 260.
- **Failed**: 0.
- **Skipped by default**: 2 guarded PostgreSQL integration tests.
- **Coverage**: 63.76%.
- **Required coverage**: 60%; passed.
- **Hypothesis seed**: `20260717`; shrinking enabled.
- **Coverage artifact**: `coverage.xml`.

### Real PostgreSQL Integration

- **Passed**: 2.
- **Failed**: 0.
- Empty database upgraded through migration `0003`.
- Repository read/write and procedure defaults passed.
- Concurrent old/new inspection ordering passed.
- Workflow status and qualification preservation passed.
- Downgrade and temporary-container cleanup passed.

### Static, Dependency and Supply Chain

- Strict mypy: passed, 94 source files.
- Bandit: passed with no findings.
- pip-audit: no known vulnerabilities.
- pip check: no broken requirements.
- compileall and `git diff --check`: passed.
- Current-change Gitleaks: no leaks.
- Full-history Gitleaks: five inherited Bidzaar JWT findings in removed files from
  commit `a4030b3…`; recorded separately, not introduced by EI-1.

### Integration and Smoke

- PostgreSQL 16 became healthy in the isolated Docker network.
- Alembic applied `0001`, `0002` and new `0003` transactionally.
- Synthetic administrator creation passed.
- Production FastAPI application and Chromium started.
- Authentication, protected routes, security headers and commit metadata passed.
- Smoke reported `SMOKE_RESULT: passed`.
- Temporary containers and networks were removed.

### Performance and External Systems

- Formal load/stress test: N/A; no route or SLO was introduced in EI-1.
- Live B2B-Center, Bidzaar, LLM, Telegram and SMTP calls: intentionally excluded.

## Defect Found and Resolved

The generated PostgreSQL test was initially only an environment guard. Build and
Test replaced it with real migration, read/write, concurrency, isolation and
downgrade scenarios. The corrected integration suite passes against temporary
PostgreSQL.

## Security and PBT Compliance

- Applicable Security Baseline controls pass for the current change.
- Historical JWT findings are inherited remediation work and are not present in
  the current change scope.
- PBT-08 passes: fixed seed, shrinking and normal CI inclusion are confirmed.
- PBT invariants/oracles/state sequences pass alongside deterministic examples.
- No blocking EI-1 Security or PBT finding remains.

## Overall Status

- **Build**: Success.
- **All applicable EI-1 tests**: Pass.
- **Coverage gate**: Pass.
- **Production image and smoke**: Pass.
- **Ready for review and the next approved unit**: Yes.
