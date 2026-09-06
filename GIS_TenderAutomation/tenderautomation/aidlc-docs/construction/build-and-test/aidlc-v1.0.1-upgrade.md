# AI-DLC v1.0.1 Upgrade Evidence

## Source

- Official repository: <https://github.com/awslabs/aidlc-workflows>
- Release tag: <https://github.com/awslabs/aidlc-workflows/releases/tag/v1.0.1>
- Rules version: `aidlc-rules/VERSION` = `1.0.1`
- Release commit: `e49341dbeb8af82758dd85e96ed7fe9bcf38a447`

## Installed changes

- Synchronized `.aidlc-rule-details/` with the official v1.0.1 rule-details tree.
- Added the Resiliency Baseline extension and its opt-in prompt.
- Applied canonical Units Generation terminology and CommonMark question spacing fixes.
- Updated the core workflow's OpenAI Codex path annotation.
- Added `.aidlc-rule-details/VERSION` for locally verifiable version tracking.
- Preserved the project-specific Graphify preamble in `CLAUDE.md`.
- Preserved TenderAutomation's JSONL guidance in `AGENTS.md` and added a
  development-task pointer to the v1.0.1 workflow.

## Validation

- Official rule-details tree comparison: passed; local differences are the
  `VERSION` marker and removal of upstream trailing whitespace in the two new
  resiliency Markdown files.
- Core workflow comparison excluding the project Graphify preamble: exact match.
- `git diff --check`: passed.
- Application test suite: 78 passed with Hypothesis seed `20260717`;
  one pre-existing Pydantic v2 deprecation warning remains.
- Graphify incremental update: passed; 2,181 nodes, 2,827 edges, 185 communities.
