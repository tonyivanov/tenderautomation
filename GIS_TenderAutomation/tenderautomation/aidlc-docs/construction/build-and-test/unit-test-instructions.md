# Unit and Property Test Execution — AI Export Integrity EI-1

## Command

```bash
.venv/bin/python -m pytest \
  --hypothesis-seed=20260717 \
  --cov=src \
  --cov-report=term-missing \
  --cov-report=xml \
  --cov-fail-under=60
```

## Expected Result

- All deterministic and property-based tests pass.
- The two real PostgreSQL tests skip unless `TEST_POSTGRESQL_URL` is set.
- Aggregate line coverage is at least 60%.
- `coverage.xml` is generated at the repository root.
- Hypothesis shrinking remains enabled with reproducible seed `20260717`.

## EI-1 Boundaries Covered

- Immutable typed contracts and timezone/provenance/batch validation.
- V3 P1/P2 eligibility and unavailable/not-found distinction.
- Exact 24-hour TTL, archive classification and null-preserving merge.
- Monotonic inspection application and workflow-status independence.
- Bounded async readiness, stable result partition and fail-closed behavior.
- Existing B2B-Center endpoint and Playwright modes remain regression-covered.
