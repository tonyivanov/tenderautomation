# Security Test Instructions — AI Export Integrity EI-1

## Commands

```bash
.venv/bin/python -m bandit -q -r src
.venv/bin/python -m pip_audit \
  --cache-dir /tmp/tenderautomation-pip-audit \
  -r requirements.txt
.venv/bin/python -m pip check
git diff --check
```

Gitleaks must scan the current change range, matching `.gitlab-ci.yml`. For
uncommitted local work, copy only `git ls-files -m -o --exclude-standard` into an
isolated temporary directory and run `gitleaks detect --no-git` there.

## Current Evidence

- Bandit: no findings.
- pip-audit: no known vulnerabilities.
- pip check: no broken requirements.
- Current modified/untracked-file Gitleaks scope: 480,854 bytes scanned, no leaks.
- CycloneDX 1.4 SBOM: valid JSON with 352 components.
- DTOs bound ID count/length and provenance keys/size.
- SQLite reads are parameterized and errors fail closed.
- Logs and result contracts contain safe categories, not credentials or payloads.

## Inherited Historical Finding

A separate full-history scan reports five old Bidzaar JWT findings in removed
files under `Разбор тендеров/Bidzaar_parsing/`, all from commit
`a4030b3fcbcacb68357cef8d55b839b6a1d0b47d`. The current change does not contain
them and the GitLab diff-range gate is clean. Treat the historical material as an
inherited repository risk: confirm the Bidzaar sessions are expired/revoked and
schedule an explicitly coordinated history rewrite if complete removal is
required.

## Security Baseline Assessment

| Rule group | Status | Evidence |
|---|---|---|
| SECURITY-03, 05, 09, 11-13, 15 | Compliant | Safe logs/errors, bounds, validation, no new secrets, fail-closed cleanup |
| SECURITY-04, 08 | Compliant unchanged | Existing security-header/auth smoke passed |
| SECURITY-01, 02, 06, 07, 14 | N/A for EI-1 | No storage encryption, intermediary, IAM, topology or monitoring change |
| SECURITY-10 | Compliant for current change | Dependency audit, image build, current-scope Gitleaks and SBOM passed |

There is no blocking finding introduced by EI-1. The five historical JWT findings
remain recorded as inherited remediation work.
