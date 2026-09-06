# Functional Design — Corrective Integration

- `PipelineOrchestrator.run_async()` owns async execution; `run()` is the CLI adapter.
- Admin acquires its in-process guard before task scheduling and releases it in `finally`.
- Tender decisions are authenticated POST operations with action allowlisting and identifier validation.
- Bidzaar treats pages as newest-first, stops at a dated `published_at <= since` boundary, normalizes datetimes to UTC, and enriches only missing deadlines.
- V3 cache initialization idempotently adds nullable `tender_id`; reads and dashboards prefer stable ID and use exact, unambiguous title matching only for legacy rows.
- Provider secrets come only from runtime environment variables; errors expose types, not provider payloads or credentials.

PBT properties: normalization idempotence, non-negative deterministic scoring, cache schema idempotence/round-trip, bounded queue values, and incremental traversal equivalence for newest-first data.
