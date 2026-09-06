# Performance Test Instructions — AI Export Integrity EI-1

Formal load and stress testing is N/A because no throughput or latency SLO was
approved and EI-1 does not connect the readiness service to a Web route.

The approved performance bounds are enforced structurally and by unit tests:

- at most 50 tenders per request;
- at most four simultaneous external operations;
- at most 30 seconds per authentication/inspection operation;
- at most 120 seconds for aggregate preparation;
- no automatic retries;
- blocking PostgreSQL/SQLite calls are moved off the event loop.

Once EI-3 exposes the route, staging performance tests should measure single and
50-item batches with cached, partial-failure and timeout mixtures. Do not run load
tests against procurement platforms without explicit authorization.
