# Local Change Reconciliation Before Anatoly MR

Status: approved for implementation by the user on 2026-07-17.

## Decision record

| Local change | Decision | Rationale |
|---|---|---|
| Bidzaar public integrator endpoint | Keep and modernize | Live read-only probe returned HTTP 200 and the expected schema; removes browser credentials from collection. |
| Bidzaar synchronous client | Replace | Conflicts with the approved async contract; migrated to `httpx.AsyncClient`. |
| B2B-Center endpoint feed | Keep as a second transport | User follow-up requires both endpoint and Playwright; the endpoint path is async, configurable, tested, and deduplicated with query results. |
| `.env`/auth-state/Hypothesis ignores | Keep | Prevents local secrets and generated test state from entering Git. |
| Graphify usage guidance | Keep | Still applies after the AI-DLC v1.0.1 upgrade. |
| Obsolete Compose `version` key | Remove | Modern Docker Compose ignores it and emits a warning. |
| Existing Graphify report | Rebuild after isolation | The mixed-worktree report was excluded from `main`; the clean rebased branch report was regenerated and may be committed. |
| Legacy build/test instruction drafts | Do not commit | They contain stale commands and unverified readiness claims. |

## Acceptance gates

- Fixed-seed test suite passes.
- Bidzaar integrator mapping, date-window clamp, deduplication, and async contract are covered.
- Docker Compose configuration validates.
- Gitleaks reports no findings in the new main commit range.
- Only explicitly classified files are staged; local B2B experiments and auth artifacts remain uncommitted.

## Verification evidence

- Live Bidzaar integrator probe: HTTP 200; expected response and item fields present.
- Clean `main` snapshot: **79 passed**; rebased MR with dual transports: **88 passed**.
- Targeted Bidzaar tests: **11 passed** before the full-suite run.
- `docker compose --env-file /dev/null config --quiet`: **passed**.
- Python compile check and `git diff --cached --check`: **passed**.
- `graphify update .`: **passed** on the isolated rebased branch, 2,205 nodes / 2,862 edges / 190 communities.
