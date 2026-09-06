# Security and quality cleanup evidence

Date: 2026-07-19

## AI-DLC scope

This increment closes the security and type-quality findings discovered during the
merge-readiness test cycle. The existing Graphify project graph was queried before
implementation to constrain changes to dependency management, web routing, external
data boundaries, scoring payloads, ORM typing, and their tests.

Out of scope: live calls to B2B Center, Bidzaar, LLM providers, Telegram, and SMTP.
Those integrations require real credentials or create external side effects. Both
B2B Center collection modes (`endpoint` and `playwright`) remain enabled and covered
by their existing contract tests.

## Baseline

- `pip-audit`: 27 vulnerability records in 6 packages.
- Bandit: 12 findings (2 medium, 10 low).
- mypy: 96 reported errors before stubs; 20 directly actionable errors after adding
  PyYAML stubs. Updating mypy and correcting the `src` layout exposed the full set of
  real internal typing errors, which were then resolved rather than suppressed.
- pytest: 88 tests.

## Implemented decisions

### Dependencies

- `python-dotenv`: 1.0.1 → 1.2.2
- `click`: 8.1.7 → 8.4.2
- `fastapi`: 0.115.5 → 0.139.2
- `jinja2`: 3.1.4 → 3.1.6
- `python-multipart`: 0.0.12 → 0.0.32
- production image `pip`: pinned to 26.1.2
- mypy: 1.11.2 → 1.20.2
- added pinned `types-PyYAML`, `types-beautifulsoup4`, Bandit, and pip-audit dev tools

The dependency graph is validated with `pip check`; known vulnerabilities are gated
with `pip-audit -r requirements.txt`.

### Bandit findings

- Dynamic SQLite column selection was replaced with two explicit static queries in
  both web routers. No user-controlled text is interpolated into SQL.
- Previously swallowed logout and Bidzaar attachment errors are now logged without
  exposing sensitive values.
- Non-security timing jitter uses `SystemRandom`.
- Deterministic P3 quality-control sampling remains seeded and is explicitly
  documented as unrelated to security decisions.

### Type safety

- Configured mypy for the repository's `src` layout with explicit package bases.
- Added concrete types for event handlers, JSON payloads, cache records, ORM JSON
  columns, Playwright pages, router sort keys, and adapter descriptors.
- Added runtime shape checks at Bidzaar/OpenRouter JSON boundaries.
- Introduced a protocol shared by the LLM waterfall clients.
- Fixed the email recipient string/list mismatch and a dataclass default factory that
  could not construct `LLMClassificationItem`.

### Regression and CI

- GitLab now runs strict mypy, Bandit, and pip-audit before image build.
- Production build runs `scripts/smoke_test.sh` before pushing an image.
- Smoke covers PostgreSQL readiness, Alembic migrations 0001/0002, admin creation,
  production application startup, Chromium launch, authentication/session behavior,
  `/tenders`, redirects, and security headers.
- bcrypt remains at 12 rounds in production; property tests temporarily use 4 rounds
  through a fixture so test runtime does not depend on container CPU performance.

## Verification evidence

| Gate | Result |
|---|---|
| pytest + Hypothesis | 88 passed |
| Coverage | 37%, XML generated |
| mypy strict | 0 errors in 84 source files |
| Bandit | 0 findings |
| pip-audit | no known vulnerabilities |
| pip check | no broken requirements |
| Python compileall | passed |
| Production Compose config | passed |
| Production Docker build | passed |
| Isolated production smoke | passed |

All smoke containers and the temporary Docker network are removed by a trap even on
failure. The disposable local verification container and image are not deployment
artifacts.
