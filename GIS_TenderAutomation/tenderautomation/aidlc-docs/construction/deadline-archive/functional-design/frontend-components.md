# Frontend Components - Deadline Archive and Reconciliation

The UI remains server-rendered Jinja2 with the existing Bootstrap styling and minimal JavaScript.

## Tender List Tabs

### Archive tab

- Label: `Архив`.
- Query value: `tab=archive`.
- Badge: count of expired tenders after platform/text filtering and before pagination.
- Order: most recently expired first; stable ID tie-break.
- Contents: all expired tenders regardless of P1/P2/Reject or workflow status.
- Stable selector: `data-testid="tenders-tab-archive"`.

### P1 and P2 tabs

- Exclude tenders for which the shared expiry predicate is true.
- Continue to include unknown-deadline tenders if their LLM queue matches.
- Do not mutate status or classification as a side effect of viewing.

### All tab

- Continues to include every record.
- Expired rows may retain the existing visual deadline warning while remaining navigable.

### Tab contracts

| Context value | Type | Meaning |
|---|---|---|
| `filters.tab` | string | Includes `archive` as an allowed value |
| `counts.archive` | nonnegative integer | Filtered, unpaginated expired count |
| `tender.expired` | boolean | Result of shared expiry predicate |
| `tender.deadline` | datetime or null | Displayed date/time or dash |

Every tab link receives a stable selector in the form `tenders-tab-{tab}`.

## Unknown Deadline Presentation

- Display the existing dash or an explicit `Дедлайн не найден` label without implying expiry.
- The row remains accessible in P1/P2 when queue rules match.
- No automatic status badge is added.

## Admin Reconciliation Form

### Placement

Add a compact section to the authenticated `/admin` page near collection controls.

### Fields and controls

- Numeric input `batch_size`, default 50, minimum 1, maximum 200.
- Submit button `Запустить исправление дедлайнов`.
- POST action handled by an admin-only route.
- Stable selectors:
  - `deadline-reconcile-form`
  - `deadline-reconcile-batch-size`
  - `deadline-reconcile-submit`
  - `deadline-reconcile-result`

### Interaction flow

```text
Admin opens /admin
  -> selects or accepts batch size
  -> submits POST
  -> server validates role and bounds
  -> shared reconciliation operation runs
  -> redirect to /admin with safe result state
  -> page displays aggregate counters
```

The submit control is disabled while the request is in progress when minimal JavaScript is available; server-side overlap rejection remains authoritative.

## Reconciliation Result

Display only:

- scanned;
- deadline updated;
- URL updated;
- unresolved;
- failed;
- remaining candidates;
- already-running message when applicable.

Do not display tender response bodies, raw exception text, credentials, cookies, tokens, or user-supplied URLs.

## Validation and Error Behavior

- Missing batch size uses 50.
- Values outside 1..200 and non-integers produce a safe validation message and no external calls.
- Non-admin users are denied by the existing server-side admin guard.
- External per-row failures appear only in aggregate counters; the form remains usable for a later rerun.
- Post-Redirect-Get prevents accidental browser resubmission.

## Accessibility and Automation

- The numeric input has an associated label and HTML `min`, `max`, and `required` constraints in addition to server validation.
- Result status uses text, not color alone.
- The Archive active state uses the existing navigation semantics.
- Stable selectors do not contain dynamic counts or IDs.

## Frontend Test Scenarios

1. Archive tab renders its count, active state, and most-recent-expiry ordering.
2. P1/P2 omit expired rows but include queue-matching unknown-deadline rows.
3. All includes the same expired rows found in Archive.
4. Archive rendering does not modify workflow status.
5. Admin form defaults to 50 and rejects 0, 201, and non-integer values.
6. Analyst/manager cannot start reconciliation.
7. Successful, partial, unresolved, and already-running aggregate results render safely.
8. All new controls expose the documented stable `data-testid` values.
