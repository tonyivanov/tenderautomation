# Change Requirements - Deadline Extraction and Archive

## Intent Analysis

- **User request**: Move tenders with expired deadlines to an Archive folder, extract trading deadlines more strictly, and open the tender page when the listing or API has no usable deadline.
- **Production correction**: P1 and P2 currently contain Bidzaar tenders with missing or expired deadlines; some persisted Bidzaar links return 404.
- **Request type**: User-facing enhancement plus collection and data-quality bug fixes.
- **Scope**: B2B-Center and Bidzaar adapters, deadline parsers, existing-data reconciliation, tender-list tabs and counts, URL normalization, and tests.
- **Complexity**: Moderate.
- **Risk**: Moderate; incorrect date or timezone handling could hide an active tender or keep an expired tender in an actionable queue.

## Validated Decisions

The answers in `deadline-archive-requirement-questions.md` were validated as complete and non-contradictory:

1. Archive is a computed folder based on deadline expiry. It does not replace workflow status.
2. Detail-page deadline fallback applies to both B2B-Center and Bidzaar.
3. A failed page lookup does not discard the tender. The tender remains without a deadline and a safe structured warning is logged.

## Functional Requirements

### FR-DEADLINE-01: Strict normalized deadline parsing

Each platform adapter shall extract the tender submission or trading deadline from the most authoritative structured field available. Parsers shall:

- reject malformed, impossible, or ambiguous values instead of silently coercing them;
- support the documented platform date and timestamp formats;
- attach the platform timezone when the source omits an offset;
- normalize persisted values to timezone-aware datetimes;
- distinguish a missing or invalid deadline from a valid deadline at midnight.

Publication dates and unrelated event dates shall not be used as the deadline.

### FR-DEADLINE-02: Detail-page fallback

When the listing or API deadline is missing or invalid, the collector shall open the canonical tender detail page and search for an explicitly labelled submission or trading deadline.

- B2B-Center endpoint collection shall reuse its HTTP session and saved cookies.
- B2B-Center Playwright collection shall reuse its authenticated browser context without disabling either retained collection transport.
- Bidzaar shall use its canonical tender URL and the available platform session or public page data.
- Detail-page extraction shall run only for records lacking a valid structured deadline.
- A page timeout, authorization failure, CAPTCHA, 404, or unrecognized layout shall not discard the tender or abort the other collection transport.

### FR-DEADLINE-03: Deadline provenance

The raw tender payload shall record whether the persisted deadline came from the listing/API or from the detail page. This diagnostic metadata shall not change the public `TenderModel.deadline` contract.

### FR-DEADLINE-04: Bidzaar canonical URLs

Bidzaar tender URLs shall be normalized from the stable `external_id` to:

`https://bidzaar.com/app/process/light/{external_id}`

The collector shall not trust an arbitrary host or path received in the integrator payload. Existing Bidzaar database rows with the legacy `/process/light/{id}` path shall be corrected during reconciliation.

### FR-ARCHIVE-01: Computed Archive folder

A tender is archived when it has a valid deadline strictly earlier than the current UTC time.

- Archive membership shall be computed from `deadline`; no `archived` workflow status or database migration is required.
- Existing statuses such as `taken`, `deferred`, and `rejected` shall remain unchanged.
- P1 and P2 shall exclude archived tenders.
- The tender list shall expose an `Архив` tab with an accurate count.
- The `Все` tab shall continue to include every tender, including archived records.
- Tenders whose deadline remains unknown after fallback shall not be marked archived.

### FR-ARCHIVE-02: Existing-data reconciliation

The change shall include an idempotent reconciliation path for existing database rows so that production is corrected without waiting for every tender to be rediscovered.

Reconciliation shall:

- attempt deadline enrichment for existing rows with no deadline;
- normalize existing Bidzaar links;
- leave a row unchanged when the platform page cannot be read;
- be safe to rerun;
- report counts without logging credentials, cookies, tokens, or tender document contents.

Because Archive membership is computed, existing rows with known expired deadlines shall appear in Archive immediately after deployment.

## Non-Functional Requirements

### NFR-DEADLINE-01: Accuracy and fail-safe behavior

- Ambiguous date text shall remain unresolved rather than be guessed.
- A tender shall be archived only from a valid timezone-aware deadline.
- External page failures shall be isolated per tender and per collection transport.
- Collection shall retain the existing partial-success behavior for B2B-Center endpoint and Playwright modes.

### NFR-DEADLINE-02: Performance and load control

- Detail pages shall not be opened when a valid structured deadline already exists.
- Requests shall use bounded timeouts and existing anti-bot/rate-limit behavior.
- Reconciliation shall support a bounded batch size so production can be repaired gradually.

### NFR-DEADLINE-03: Security

- Detail URLs shall be constructed or validated against the configured platform host to prevent arbitrary outbound requests.
- Authentication material and full external response bodies shall never be written to logs.
- Error logs shall contain only platform, tender ID, extraction stage, and safe error category.

### NFR-DEADLINE-04: Testability

- Example-based tests shall cover known listing and detail-page formats, timezone boundaries, expired/active classification, missing deadlines, 404 fallback, and dual B2B-Center transports.
- Hypothesis tests shall verify that deadline parsers never raise for arbitrary text, normalization is idempotent, and Archive classification never archives a missing or invalid deadline.
- Router tests shall verify P1/P2 exclusion, Archive inclusion/counts, All inclusion, and workflow-status preservation.
- Reconciliation tests shall verify idempotency and safe partial failure.
- This iteration shall raise aggregate line coverage for `src/` from the last verified 37% baseline to at least 60%.
- GitLab CI and the documented local merge command shall enforce the threshold with `--cov-fail-under=60` while continuing to generate terminal and Cobertura XML reports.
- Coverage growth shall exercise meaningful success, boundary, and error behavior across existing under-tested components; production modules shall not be omitted merely to satisfy the percentage.

## Acceptance Criteria

1. A tender with a valid deadline before the current time appears in `Архив` and not in P1 or P2.
2. Archiving does not alter the tender's existing workflow status.
3. A tender with a future deadline remains eligible for P1 or P2.
4. A tender without a listing/API deadline is enriched from its detail page when an explicit deadline is available.
5. If detail-page extraction fails, the tender is preserved with `deadline = null` and collection continues.
6. Both B2B-Center endpoint and Playwright collection paths remain enabled and independently failure-tolerant.
7. Bidzaar links use the canonical `/app/process/light/{external_id}` path and existing broken links are reconciled.
8. Existing rows with known expired deadlines move into the computed Archive immediately; missing deadlines can be backfilled in bounded batches.
9. Aggregate `src/` line coverage is at least 60%, and the test command fails below that threshold.
10. Unit, property-based, router/integration, strict mypy, Bandit, dependency, and smoke gates pass.

## Stage Assessment

- **User Stories**: Execute; this changes the analyst's P1/P2 workflow and adds a new Archive navigation path.
- **Application Design**: Skip; existing adapter, repository, and router boundaries are sufficient.
- **Units Generation**: Skip; this is one coordinated change across existing units.
- **Functional Design**: Execute; source precedence, fallback isolation, reconciliation, and computed Archive behavior need explicit design.
- **NFR Requirements/NFR Design**: Skip as standalone stages; applicable security, reliability, and testing constraints are complete above.
- **Infrastructure Design**: Skip; no new infrastructure is introduced.
- **Code Generation**: Execute after approved planning and design.
- **Build and Test**: Execute, including the project-wide 60% coverage gate and focused smoke coverage.

## Security Compliance

| Rule | Status | Rationale |
|---|---|---|
| SECURITY-03 | Compliant | Safe structured logging excludes secrets and response bodies |
| SECURITY-05 | Compliant | Date and URL inputs are strictly validated before use |
| SECURITY-09 | Compliant | External failures do not expose internal details or abort unrelated work |
| SECURITY-12 | Compliant | Existing session mechanisms are reused; no credentials are added to code |
| SECURITY-15 | Compliant | External calls have bounded failure handling and fail safely per tender |
| SECURITY-01, 02, 04, 06-08, 10, 11, 13, 14 | N/A | No storage encryption, ingress, authorization, dependency, IAM, or monitoring architecture is changed |

No blocking security findings were identified at Requirements Analysis.

## Property-Based Testing Compliance

- **PBT-01**: Applicable properties are strict type/range invariants, normalization idempotence, safe arbitrary-text parsing, and Archive classification invariants.
- **PBT-03**: Deadline and Archive invariants require generated boundary coverage.
- **PBT-04**: URL/date normalization and reconciliation shall be idempotent.
- **PBT-07 through PBT-10**: Domain-specific date/text generators, reproducible Hypothesis execution, and complementary example tests are required.
- **PBT-02, PBT-05, PBT-06**: N/A at this stage; no lossless formatter inverse, separate oracle implementation, or new state machine is required.

No blocking PBT findings were identified at Requirements Analysis.
