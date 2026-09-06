# Build and Test Evidence — Merge Readiness

Status: local quality gates passed on 2026-07-17.

- `pytest --hypothesis-seed=20260717`: **88 passed**, one Pydantic deprecation warning.
- `git diff --check`: **passed**.
- Branch-specific secret-pattern scan and `.env`/egg-info/`docker-com` tree check: **passed**.
- Production `docker compose ... config --quiet` with placeholders: **passed**.
- `git merge-base --is-ancestor main HEAD`: **passed**.
- `graphify update .`: **passed**, 2,205 nodes / 2,862 edges / 190 communities.

CI now runs fixed-seed tests and Gitleaks before image build; build validates Compose before push.
Gitleaks is constrained to newly introduced commit history: MR diff-base to head, feature-branch
merge-base to head, or the new default-branch push range. This avoids treating five historical
JWT/session findings in the initial `main` commit as findings introduced by every MR.

Pipeline-failure verification on 2026-07-17:

- Exact Gitleaks v8.24.2 full-history reproduction identified the five GitLab findings in
  commit `a4030b3`; none were introduced by this branch.
- `main..HEAD`: **4 commits scanned, no leaks found**.
- The revised GitLab MR script executed in the pinned container image: **no leaks found**.
- CI YAML parsing and the commit-scope regression test: **passed**.

AI-DLC workflow rules were subsequently upgraded to v1.0.1; validation evidence is
recorded in `aidlc-v1.0.1-upgrade.md`.

Post-main-rebase verification:

- B2B-Center retains both endpoint and Playwright transports with configurable modes,
  partial-source failure isolation, and stable-ID deduplication.
- Bidzaar collection uses the public integrator API; manual private session state is
  isolated to opt-in deep analysis.
- Targeted transport/auth suites: **38 passed**.
- Full fixed-seed suite: **88 passed**; server Compose, compile, and diff gates passed.
- Final Gitleaks v8.24.2 `main..HEAD`: **6 commits scanned, no leaks found**.

Human action: rotate every credential previously committed to `fix/expired-tenders-filter`; code cleanup cannot revoke exposed credentials.
