# Story Generation Plan - Deadline Extraction and Archive

## Context

- **Approved requirements**: `aidlc-docs/inception/requirements/deadline-archive-change.md`
- **Existing personas**: analyst, BD manager, and administrator in `aidlc-docs/inception/user-stories/personas.md`
- **Existing story affected**: US-04, qualified-tender list and tender-card workflow.
- **Artifacts to update in place**: `stories.md` and `personas.md`; no duplicate story documents will be created.

## Proposed Methodology

Use a **feature-based plus user-journey hybrid**:

1. Extend the analyst journey from P1/P2 to Archive while preserving workflow status.
2. Add a collection data-quality story covering strict deadline extraction and safe detail-page fallback.
3. Add an administrator reconciliation story for existing missing deadlines and broken Bidzaar links.

This keeps the stories small enough to test while preserving traceability to the approved functional requirements.

## Other Breakdown Options Considered

- **Persona-based only**: clear ownership but duplicates shared deadline rules across analyst and administrator stories.
- **Domain-based only**: clean adapter/web separation but obscures the end-to-end user outcome.
- **Single epic**: compact but too broad to satisfy INVEST testability.

## Questions

Fill every `[Answer]:` with one letter. Choose `X` when none of the proposed behaviors matches the intended workflow.

### Question 1
How should an administrator start reconciliation of existing tenders with missing deadlines or broken Bidzaar links?

A) From an authenticated admin-panel action that processes a bounded batch and shows the result; also expose the same operation through CLI for production support (recommended)

B) Through CLI only; no new admin-panel control

C) Automatically after every collection until the backlog is empty; no manual control

X) Other (please describe after [Answer]: tag below)

[Answer]: A

### Question 2
How should tenders be ordered inside the Archive folder?

A) Most recently expired first, then older tenders (recommended)

B) Oldest expired first

C) Preserve P1 before P2, then sort each group by most recently expired

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Generation Checklist

- [x] Validate all answers for completeness, ambiguity, and contradictions.
- [x] Obtain explicit approval of this story-generation plan.
- [x] Update the existing analyst persona with the active-to-Archive workflow and unknown-deadline behavior.
- [x] Update the existing administrator persona with bounded reconciliation responsibility.
- [x] Amend US-04 so P1/P2 exclude expired tenders and Archive preserves status.
- [x] Add a strict deadline and safe detail-page fallback story covering both platforms.
- [x] Add an existing-data reconciliation and Bidzaar URL repair story.
- [x] Express key behavior with Given/When/Then and supporting checklists.
- [x] Map every new acceptance criterion to FR-DEADLINE-01 through FR-DEADLINE-04 or FR-ARCHIVE-01 through FR-ARCHIVE-02.
- [x] Verify that each story is Independent, Negotiable, Valuable, Estimable, Small, and Testable.
- [x] Verify Security Baseline and Property-Based Testing applicability in the story acceptance criteria.
- [x] Add the permanent 60% aggregate `src/` line-coverage threshold to the shared Definition of Done for these stories.
- [x] Present generated stories and personas for explicit approval before Workflow Planning.

## Expected Story Set

1. **Analyst Archive navigation** - active queues remain actionable and expired tenders remain discoverable.
2. **Reliable deadline acquisition** - structured dates take precedence and missing dates use safe detail-page fallback.
3. **Administrator reconciliation** - existing rows are repaired in bounded, idempotent batches with safe reporting.

## Mandatory Artifact Compliance

- `stories.md` remains the canonical story artifact and will contain INVEST stories with acceptance criteria.
- `personas.md` remains the canonical persona artifact and will map personas to the new stories.
- Existing content will be modified in place rather than copied to parallel files.
- The story Definition of Done will require meaningful tests that bring total project line coverage to at least 60%; this is a project NFR rather than a standalone user feature.
