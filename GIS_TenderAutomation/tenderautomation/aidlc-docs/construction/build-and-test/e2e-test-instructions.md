# End-to-End Test Instructions — AI Export Integrity EI-1

EI-1 has no new user-facing route, so its applicable end-to-end boundary is the
existing production container smoke:

```text
image -> isolated PostgreSQL -> Alembic 0001/0002/0003 -> synthetic admin
-> FastAPI -> authentication and protected pages -> Chromium -> cleanup
```

Run:

```bash
scripts/smoke_test.sh tenderautomation:ei1-local
```

Success is `SMOKE_RESULT: passed`. AI ZIP behavior and concrete platform
inspection are deferred to EI-2/EI-3 and therefore are not claimed by this smoke.
