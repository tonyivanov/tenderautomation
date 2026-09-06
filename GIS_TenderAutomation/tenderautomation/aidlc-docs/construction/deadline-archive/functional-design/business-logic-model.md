# Business Logic Model - Deadline Extraction and Archive

## Scope and Traceability

This design implements US-04, US-08, and US-09 across existing Core, Adapter, Web, and CLI boundaries. It introduces no database entity and no `archived` workflow status.

## 1. Normalized Deadline Pipeline

### Inputs

- Structured listing/API value, if present.
- Platform timezone from the adapter descriptor; `Europe/Moscow` is the current default for both platforms when the source has no offset.
- Explicitly labelled detail-page date candidates, used only when the structured value is absent or invalid.

### Transformation

```text
structured value
  -> strict parse
  -> if valid: attach/convert timezone, normalize to UTC, source = listing|api
  -> if missing or invalid: open canonical detail page
  -> extract labelled candidates by priority
  -> strict parse selected candidate
  -> if valid: attach/convert timezone, normalize to UTC, source = detail
  -> otherwise: deadline = null, source = unresolved
```

Date-only values are interpreted as `23:59:59` in the platform timezone before UTC normalization. A malformed, impossible, unlabelled, or conflicting date is unresolved rather than guessed.

### Detail Candidate Priority

1. End of application/bid acceptance: labels equivalent to “окончание приёма заявок”, “приём предложений до”, “acceptance end”, or explicit “deadline”.
2. Trading/auction date: labels equivalent to “дата торгов”, “проведение аукциона”, or “auction date”.
3. Unlabelled page dates are ignored.

If two valid candidates in the same priority group disagree, extraction returns unresolved. A lower-priority value is used only when the higher-priority group has no valid candidate.

## 2. B2B-Center Collection Flow

### Endpoint transport

1. Fetch a listing page with the existing HTTP client, cookies, timeout, and rate limits.
2. Parse each row and strictly evaluate `deadline_raw`.
3. When the value is missing or invalid, request that row's canonical detail URL through the same client and cookies.
4. Parse explicit deadline labels and add `deadline_raw`, `deadline_source`, and optional safe extraction state to the raw payload.
5. A detail failure affects only that row; listing pagination continues.

### Playwright transport

1. Keep the existing search page for query navigation.
2. Reuse the authenticated browser context for a separate reusable detail page.
3. Open a detail page only for a row without a valid listing deadline.
4. Apply the same label precedence and parser contract as the endpoint transport.
5. Close the reusable detail page and browser context through existing cleanup paths.

### Dual-source merge

Deduplication by `external_id` merges rather than blindly keeps the first record:

- valid deadline beats missing deadline;
- structured listing deadline beats detail-derived deadline when both are valid;
- non-empty buyer/title data may fill missing fields but does not overwrite existing valid data;
- source query metadata is retained without changing the stable tender ID.

One transport failure does not discard results from the other. Collection fails only under the existing rule that every configured transport fails.

## 3. Bidzaar Collection Flow

1. Fetch integrator API items with the existing incremental boundary.
2. Derive `external_id` from the stable item identifier/link suffix.
3. Construct the canonical URL as `https://bidzaar.com/app/process/light/{external_id}` regardless of the host/path supplied in the payload.
4. Strictly parse `acceptanceEndDate`, then `finishDate` only as the documented structured fallback.
5. If neither is valid, open the canonical page using available public/session context and apply detail candidate priority.
6. Persist active, unknown-deadline, and already-expired fetched tenders; expiry determines presentation, not collection deletion.

A 404, authorization failure, timeout, or unknown page structure leaves the deadline unresolved and does not discard the tender.

## 4. Archive Classification

The single business predicate is:

```text
is_expired(deadline, now_utc):
    if deadline is null or lacks timezone information:
        return false
    return deadline converted to UTC < now_utc
```

Consequences:

- P1/P2 exclude `is_expired = true`.
- Archive includes every expired tender, regardless of LLM queue or workflow status.
- Archive sorts by deadline descending, then stable tender ID.
- All includes active, unknown-deadline, and archived tenders.
- Unknown or timezone-invalid deadlines remain visible under their existing queue/status but are never archived.
- No operation changes `TenderStatus` merely because time passes.

Counts are computed after platform and text filters and before pagination so badges describe the filtered result set.

## 5. Existing-Data Reconciliation

### Candidate selection

A record is a candidate when either condition is true:

- `deadline IS NULL`; or
- platform is Bidzaar and URL differs from the canonical URL for `external_id`.

Candidates are selected deterministically by most recent `updated_at`, then ID, with a user-supplied batch size from 1 to 200. Default is 50.

### Per-record operation

1. Normalize the Bidzaar URL when required.
2. If deadline is null, request the canonical detail page through the platform-specific enrichment boundary.
3. Set deadline and provenance only when a valid explicit candidate is found.
4. Preserve title, qualification, workflow status, actions, and existing non-null deadline.
5. Commit successful field corrections independently so one failure does not roll back other records.

### Result counters

```text
scanned
deadline_updated
url_updated
unresolved
failed
remaining_candidates
already_running
```

A reconciliation run is idempotent: after all correctable fields are normalized, repeating it produces zero updates. Admin and CLI entry points invoke the same operation and return the same counters.

Overlapping runs are rejected as `already_running` to avoid duplicate platform traffic. The lock is released on success and error paths.

## 6. Failure and Logging Model

External failure categories are limited to safe values such as `timeout`, `not_found`, `unauthorized`, `captcha`, `invalid_markup`, and `network_error`.

Logs may contain platform, tender ID, source stage, safe category, and aggregate counters. They must not contain credentials, cookies, tokens, full URLs with untrusted query strings, or response bodies.

## 7. Testable Properties

| Property | Category | Expected invariant |
|---|---|---|
| Arbitrary text parsing | Invariant | Never raises; returns null or timezone-aware datetime |
| Date-only normalization | Invariant | Local time is always `23:59:59` before UTC conversion |
| UTC normalization | Idempotence | Normalizing an already normalized deadline changes nothing |
| Canonical Bidzaar URL | Idempotence | Canonicalizing twice equals canonicalizing once |
| Missing deadline | Invariant | Null is never expired |
| Expiry monotonicity | Invariant | Once expired at time `t`, it remains expired for every later time |
| Status independence | Invariant | Changing workflow status does not change Archive membership |
| Merge quality | Invariant | Merging duplicate raw rows never replaces a valid deadline with null |
| Batch bound | Range invariant | Processed count is between zero and requested bound, never above 200 |
| Reconciliation rerun | Idempotence | A second successful run produces no additional field changes |

Example tests remain mandatory for known platform formats, precedence conflicts, final-day behavior, 404/timeouts, and admin authorization.
