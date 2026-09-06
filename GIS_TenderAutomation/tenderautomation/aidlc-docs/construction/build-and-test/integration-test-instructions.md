# Integration Test Instructions — AI Export Integrity EI-1

## PostgreSQL Migration and Persistence

Start an isolated PostgreSQL instance and export:

```bash
export DATABASE_URL='postgresql://ei1:ei1@127.0.0.1:55432/ei1?sslmode=disable'
export TEST_POSTGRESQL_URL="$DATABASE_URL"
.venv/bin/python -m pytest -q tests/integration/test_export_persistence.py
```

The suite:

- upgrades the empty database through `0001`, `0002` and `0003`;
- verifies all new procedure columns;
- writes and reads a tender through `TenderRepository`;
- races older and newer verified inspections and asserts the newer result wins;
- verifies workflow status and qualification are preserved;
- checks a missing-row operation cannot damage an existing tender;
- downgrades back to the empty schema during cleanup.

## Production Container Integration

```bash
scripts/smoke_test.sh tenderautomation:ei1-local
```

Smoke creates a temporary network and PostgreSQL, applies migration `0003`,
creates a synthetic admin, starts the production FastAPI image, verifies
authentication, protected pages, security headers, commit metadata and Chromium,
then removes all temporary resources.

Live procurement-platform and LLM calls are intentionally excluded.
