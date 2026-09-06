# Functional Design Plan - Deadline and Archive Change Unit

## Unit Context

This change unit coordinates existing ownership boundaries rather than creating a new deployable unit:

- **Core**: expiry predicate, reconciliation contract, bounded repository operations, counters, and shared CLI orchestration.
- **Adapters**: strict source parsing, canonical URLs, conditional detail-page fallback, provenance, and partial failure isolation.
- **Web**: computed Archive tab, P1/P2 filtering, admin reconciliation action, validation, and result display.
- **Tests**: deterministic fixtures, Hypothesis properties, integration contracts, and the project-wide 60% coverage gate.

### Story Traceability

- **US-04**: active queues, Archive, ordering, status preservation, and unknown deadlines.
- **US-08**: strict deadline acquisition and safe detail-page fallback.
- **US-09**: bounded admin/CLI reconciliation and Bidzaar URL repair.

## Design Questions

Fill every `[Answer]:` with one letter. Select `X` only when none of the proposed business rules matches the intended behavior.

### Question 1
How should a valid deadline containing only a calendar date, without a time, be interpreted?

A) As the end of that date in the platform timezone (`23:59:59`), so the tender is not archived at the start of its final day (recommended)

B) As the start of that date (`00:00:00`)

X) Other (please describe after [Answer]: tag below)

[Answer]: A

### Question 2
Which explicitly labelled date should be treated as the tender deadline when the detail page contains several procurement dates?

A) First prefer the end of application/bid acceptance; if absent, use an explicitly labelled trading or auction date; never infer a deadline from an unlabelled date (recommended)

B) Use only the end of application/bid acceptance; ignore the trading or auction date

C) Use the earliest future date among explicitly labelled application, trading, and auction dates

X) Other (please describe after [Answer]: tag below)

[Answer]: A

### Question 3
What batch-size bounds should apply to admin and CLI reconciliation?

A) Default 50 records, maximum 200 per run (recommended)

B) Default 100 records, maximum 1000 per run

C) Fixed server configuration only; the administrator cannot select a batch size

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Functional Design Checklist

- [x] Validate every answer for completeness, ambiguity, and contradictions.
- [x] Define the normalized deadline value, source provenance, and canonical URL concepts.
- [x] Define strict parsing and timezone rules, including date-only behavior.
- [x] Define source precedence for listing/API and detail-page labels.
- [x] Define B2B-Center endpoint and Playwright fallback flows without removing either transport.
- [x] Define Bidzaar canonical URL and detail fallback behavior.
- [x] Define failure isolation for timeout, 404, CAPTCHA, authentication, and unknown markup.
- [x] Define one timezone-aware Archive predicate shared by Web and reconciliation logic.
- [x] Define Archive count, filter, ordering, All-tab behavior, and workflow-status preservation.
- [x] Define reconciliation candidate selection, batch validation, idempotency, partial success, counters, and safe reporting.
- [x] Define admin and CLI interactions against the same business operation.
- [x] Identify all testable properties required by PBT-01.
- [x] Create `business-logic-model.md`.
- [x] Create `business-rules.md`.
- [x] Create `domain-entities.md`.
- [x] Create `frontend-components.md`.
- [x] Verify Security Baseline and Property-Based Testing compliance.
- [x] Present all functional-design artifacts for explicit approval before Code Generation planning.

## Planned Artifacts

Artifacts will be stored under `aidlc-docs/construction/deadline-archive/functional-design/`:

1. `business-logic-model.md` - end-to-end transformations and alternative/error flows.
2. `business-rules.md` - normative precedence, validation, Archive, reconciliation, and logging rules.
3. `domain-entities.md` - value objects and result contracts; no new database entity is planned.
4. `frontend-components.md` - Archive tab and admin reconciliation form/result behavior.

## Design Constraints

- No database migration or `archived` workflow status.
- No live-platform dependency in deterministic tests.
- No removal of B2B-Center endpoint or Playwright collection.
- No arbitrary external URL fetching; hosts and canonical paths are platform-controlled.
- No credential, cookie, token, or external response-body exposure.
- No reduction of the 60% coverage denominator to satisfy the threshold.
