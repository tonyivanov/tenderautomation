# Domain Entities - Deadline Extraction and Archive

These are logical contracts. They may be represented with existing Pydantic models, typed records, or dataclasses during implementation. No database migration is required.

## NormalizedDeadline

Represents a confirmed deadline and its provenance.

| Field | Type | Constraint |
|---|---|---|
| `value` | timezone-aware datetime | Normalized to UTC |
| `source` | enum | `listing`, `api`, or `detail` |
| `label_kind` | enum or null | `acceptance_end` or `trading_date` |
| `date_only` | boolean | True when `23:59:59` end-of-day semantics were applied |

Only `value` maps to `TenderModel.deadline`. Provenance fields map to keys inside existing `raw_data`.

## DeadlineCandidate

An internal parsed-or-unparsed value found in a structured source or detail page.

| Field | Type | Constraint |
|---|---|---|
| `raw_text` | string | Bounded source text, never logged verbatim |
| `source` | enum | `listing`, `api`, or `detail` |
| `label_kind` | enum or null | Explicit recognized label or null |
| `priority` | integer | Acceptance end before trading date |
| `parsed_value` | datetime or null | Timezone-aware when non-null |
| `date_only` | boolean | Indicates end-of-day adjustment |

Candidates are ephemeral and are not persisted as a new entity.

## DeadlineExtractionOutcome

| Field | Type | Constraint |
|---|---|---|
| `deadline` | `NormalizedDeadline` or null | Null when unresolved |
| `state` | enum | `resolved`, `missing`, `invalid`, `ambiguous`, `external_failure` |
| `error_category` | enum or null | Safe category only |

The outcome deliberately excludes credentials, response bodies, and raw exception messages.

## ArchiveMembership

A derived value, not persisted.

| Field | Type | Definition |
|---|---|---|
| `expired` | boolean | `aware_deadline_utc < now_utc` |
| `deadline` | datetime or null | Existing tender deadline |
| `workflow_status` | TenderStatus | Carried through unchanged |

Archive membership depends only on deadline and current time, never on status or LLM queue.

## ReconciliationCommand

| Field | Type | Constraint |
|---|---|---|
| `batch_size` | integer | Default 50; inclusive range 1..200 |
| `requested_by` | string | Authenticated admin ID or CLI operator label |
| `source` | enum | `admin` or `cli` |

The command does not accept a URL, platform credential, arbitrary query, or tender ID list.

## ReconciliationResult

| Field | Type | Constraint |
|---|---|---|
| `scanned` | nonnegative integer | At most requested batch size |
| `deadline_updated` | nonnegative integer | At most scanned |
| `url_updated` | nonnegative integer | At most scanned |
| `unresolved` | nonnegative integer | At most scanned |
| `failed` | nonnegative integer | At most scanned |
| `remaining_candidates` | nonnegative integer | Count after current run |
| `already_running` | boolean | True means no rows processed |

A row can update both deadline and URL, so `deadline_updated + url_updated` may exceed `scanned`. `unresolved` applies to a deadline lookup without a valid result; `failed` represents a safe operational failure.

## Existing Tender Data Mapping

| Existing field | New behavior |
|---|---|
| `TenderModel.deadline` | Confirmed timezone-aware deadline or null |
| `TenderModel.url` | Canonical Bidzaar URL; existing B2B canonical URL retained |
| `TenderModel.raw_data.deadline_source` | `listing`, `api`, `detail`, or `unresolved` |
| `TenderModel.raw_data.deadline_label_kind` | `acceptance_end`, `trading_date`, or null |
| `TenderModel.status` | Never changed by Archive or reconciliation |

## Relationships

- One Tender has zero or one confirmed NormalizedDeadline.
- One extraction attempt considers zero or more DeadlineCandidates and produces one DeadlineExtractionOutcome.
- One ReconciliationCommand produces one ReconciliationResult across up to `batch_size` existing Tenders.
- ArchiveMembership is recalculated for each Tender at query/render time.

## Test Generators

- Labelled date strings across valid/invalid calendar boundaries and supported formats.
- Timezone-aware instants around equality, one microsecond before, and one microsecond after `now`.
- Date-only values around month/year/leap-day boundaries.
- External IDs with valid UUID-like and opaque suffix shapes, excluding path separators.
- Existing tender records with independent combinations of null deadline, canonical URL, legacy URL, and workflow status.
- Batch sizes covering below-minimum, minimum, default, maximum, and above-maximum values.
