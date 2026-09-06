# Business Rules - Deadline Extraction and Archive

## Deadline Rules

**BR-DA-01**: A persisted deadline must be timezone-aware. Archive classification must not use naive datetimes.

**BR-DA-02**: A date-only source value represents the end of that platform-local date at `23:59:59`.

**BR-DA-03**: Explicit source offsets take precedence over the platform default timezone.

**BR-DA-04**: Structured listing/API values take precedence over detail-page values when valid.

**BR-DA-05**: Detail extraction prefers application/bid acceptance end over trading/auction date.

**BR-DA-06**: Unlabelled dates, invalid calendar values, and conflicting valid dates in the same priority group are unresolved.

**BR-DA-07**: Publication, clarification, contract-signing, and result-announcement dates must never become the deadline.

**BR-DA-08**: Deadline provenance is one of `listing`, `api`, `detail`, or `unresolved` and is stored in raw diagnostic data.

## Platform Rules

**BR-DA-09**: Both B2B-Center endpoint and Playwright transports remain enabled according to the descriptor and independently failure-tolerant.

**BR-DA-10**: A detail page is opened only when the current record lacks a valid structured deadline.

**BR-DA-11**: B2B-Center endpoint fallback reuses its HTTP cookies/session; Playwright fallback reuses its authenticated browser context.

**BR-DA-12**: Deduplication must retain the best known deadline and must not replace a valid value with null.

**BR-DA-13**: Bidzaar URLs are constructed exclusively as `https://bidzaar.com/app/process/light/{external_id}`. An arbitrary API host/path is not fetched.

**BR-DA-14**: Bidzaar collection persists fetched tenders regardless of whether a known deadline is already expired; presentation handles Archive membership.

**BR-DA-15**: Detail requests use bounded timeouts and existing platform rate/anti-bot controls.

## Archive Rules

**BR-DA-16**: A tender is expired exactly when a valid timezone-aware deadline converted to UTC is strictly earlier than current UTC time.

**BR-DA-17**: Equality with current time is not expired until the clock advances beyond the deadline.

**BR-DA-18**: P1 and P2 exclude expired tenders but may contain tenders whose deadline remains unknown.

**BR-DA-19**: Archive contains all expired tenders regardless of queue, platform, or workflow status.

**BR-DA-20**: Archive membership does not write or replace `TenderStatus`.

**BR-DA-21**: Archive order is deadline descending, then tender ID for deterministic ties.

**BR-DA-22**: All continues to show every tender.

**BR-DA-23**: Tab counts are calculated after platform/text filtering and before pagination.

## Reconciliation Rules

**BR-DA-24**: Reconciliation accepts an integer batch size from 1 through 200; default is 50. Invalid input is rejected before external calls.

**BR-DA-25**: Candidates are limited to null deadlines or noncanonical Bidzaar URLs.

**BR-DA-26**: Reconciliation never overwrites an existing non-null deadline and never changes title, qualification, workflow status, or action history.

**BR-DA-27**: Successful corrections are committed per record; a failed row does not roll back other rows.

**BR-DA-28**: Admin and CLI entry points call the same operation and expose the same result counters.

**BR-DA-29**: Repeating reconciliation is safe and produces no new changes for already corrected rows.

**BR-DA-30**: Only one reconciliation run may actively issue external detail requests; another invocation returns `already_running` without work.

## Web and Authorization Rules

**BR-DA-31**: The Archive tab requires the existing authenticated user session.

**BR-DA-32**: Starting reconciliation requires a server-side `admin` role check and a POST request.

**BR-DA-33**: The admin form follows Post-Redirect-Get and shows only safe aggregate counters.

**BR-DA-34**: All new interactive controls use stable `data-testid` values.

## Security Rules

**BR-DA-35**: Detail requests are restricted to configured platform HTTPS hosts and canonical paths. Redirects to a different host are rejected.

**BR-DA-36**: Credentials, tokens, cookies, tender documents, and response bodies are never logged or rendered in reconciliation results.

**BR-DA-37**: External failures are mapped to a safe category and do not expose exception text to end users.

**BR-DA-38**: Resources such as HTTP clients, pages, contexts, and locks are released on success and error paths.

## Test and Coverage Rules

**BR-DA-39**: Unit/property tests use a reproducible Hypothesis seed and retain shrinking.

**BR-DA-40**: Live platforms are excluded from deterministic merge gates; HTTP and browser behavior use representative fixtures/mocks.

**BR-DA-41**: Aggregate line coverage for `src/` must be at least 60%; local and GitLab commands fail below the threshold.

**BR-DA-42**: Production modules must not be omitted from coverage solely to meet the threshold.

## Security Baseline Compliance

| Rule | Status | Design evidence |
|---|---|---|
| SECURITY-03 | Compliant | Safe structured fields and aggregate counters only |
| SECURITY-05 | Compliant | Batch bounds, strict dates, canonical IDs and URLs |
| SECURITY-08 | Compliant | Authenticated Archive and admin-only mutation |
| SECURITY-09 | Compliant | Generic external failure categories |
| SECURITY-12 | Compliant | Existing credential/session mechanisms only |
| SECURITY-15 | Compliant | Per-row handling and resource cleanup |
| Remaining rules | N/A | No infrastructure, IAM, dependency, or storage-encryption change |

No blocking security finding exists in this design.

## PBT Compliance

| Rule | Status | Design evidence |
|---|---|---|
| PBT-01 | Compliant | Properties identified in the business logic model |
| PBT-03 | Compliant | Parser, expiry, status, merge, and batch invariants |
| PBT-04 | Compliant | UTC/URL normalization and reconciliation idempotency |
| PBT-07 | Compliant | Domain generators required for labelled dates, timezones, and records |
| PBT-08 | Compliant | Fixed/logged seed and normal Hypothesis shrinking |
| PBT-09 | Compliant | Existing Hypothesis framework |
| PBT-10 | Compliant | Known formats and failures retain example tests |
| PBT-02, PBT-05, PBT-06 | N/A | No inverse, separate oracle, or new state machine is required |

No blocking PBT finding exists in this design.
