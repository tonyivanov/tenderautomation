# AGENTS.md — TenderAutomation AI Agent Instructions

## Software development workflow

For software-development requests, first read and follow `CLAUDE.md`, which contains
the vendored AI-DLC v1.0.1 core workflow. Load stage-specific rules from
`.aidlc-rule-details/` as directed there. This development-workflow instruction
takes precedence over the tender-analysis instructions below when the task changes
application code, tests, deployment configuration, or architecture.

The remaining instructions apply when analyzing exported tender JSONL data.

This file provides context for any AI agent (Claude, ChatGPT, Gemini, etc.) analyzing tenders exported from the TenderAutomation system.

## How to use this file

1. Load this file as context before analyzing the JSONL file
2. Load the `tenders_YYYY-MM-DD.jsonl` file
3. For each tender, evaluate relevance to the company profile below
4. Assign a tier and provide a brief rationale

## JSONL Data Schema

Each line in the JSONL file is a JSON object with these fields:

| Field | Type | Description |
|---|---|---|
| `id` | string | Unique tender ID: `{platform}_{external_id}` |
| `platform` | string | Source platform: `bidzaar` or `b2bcenter` |
| `title` | string | Tender title |
| `buyer` | string\|null | Customer organization name |
| `budget` | string\|null | Maximum contract price in rubles (e.g. `"1500000.00"`) |
| `deadline` | string\|null | Submission deadline (ISO 8601) |
| `url` | string | Link to original tender on the platform |
| `description` | string\|null | Tender description (may be null for listings) |
| `prefilter_score` | integer | Keyword match score (0 = not matched, higher = more keywords) |
| `qualification_tier` | string | Always `"qualified"` in this export |
| `matched_keywords` | array | List of keywords that matched |
| `published_at` | string\|null | Publication date (ISO 8601) |
| `exported_at` | string | Export timestamp (ISO 8601) |

## Tier Classification

Assign one of these tiers to each tender:

| Tier | Meaning | When to use |
|---|---|---|
| ⭐ | **Direct match** | Clearly within company expertise, high probability of winning |
| 🟡 | **Worth reviewing** | Potentially relevant, requires deeper review of full TZ |
| 🟠 | **Heavy competition** | Relevant but likely many strong competitors |
| 🔴 | **Noise** | Not relevant despite keyword match |

## Output Format

For each tender, provide:
```
[ID] ⭐/🟡/🟠/🔴 — One sentence rationale
```

Example:
```
[bidzaar_12345] ⭐ — Infrastructure audit for a bank using Kubernetes and cloud migrations — core GIS expertise.
[b2bcenter_99876] 🔴 — Title matches "мониторинг" but refers to video surveillance, not IT infrastructure monitoring.
```

{{SEMANTIC_PROFILE}}

## Important notes

- Focus on technical substance, not just keyword matches
- A high `prefilter_score` means many keywords matched, but doesn't guarantee relevance
- Check `buyer` — government agencies and state-owned companies often have longer procurement cycles
- `budget: null` means price not specified in listing — don't disqualify based on this
