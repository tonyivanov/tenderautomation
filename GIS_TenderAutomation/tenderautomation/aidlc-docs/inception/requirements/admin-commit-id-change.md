# Change Requirements - Commit ID on Admin Navigation Bar

## Intent Analysis

- **User request**: Display the deployed commit ID in the top bar of `/admin`.
- **Request type**: User-interface enhancement and deployment traceability improvement.
- **Scope**: Web admin route and template, runtime configuration, production image build metadata, and regression tests.
- **Complexity**: Simple.
- **Risk**: Low; no database, platform integration, or public API contract changes.

## Functional Requirements

### FR-COMMIT-01: Production build identity

The production Docker image shall contain the Git commit SHA supplied by GitLab CI at
image build time. Runtime code shall not depend on a `.git` directory being present in
the image.

### FR-COMMIT-02: Admin-only display

The top navigation bar rendered for `GET /admin` shall display the first eight characters
of the deployed commit SHA in a compact, readable form.

The commit label shall not be added to unrelated pages because only the admin route needs
deployment diagnostics.

### FR-COMMIT-03: Safe fallback

When build metadata is absent, such as during a local source run, the admin top bar shall
display `unknown` rather than fail the request or execute a Git subprocess.

### FR-COMMIT-04: Stable selector

The rendered commit label shall have a stable `data-testid` attribute for automated UI
and smoke testing.

## Non-Functional Requirements

### NFR-COMMIT-01: Security

- The commit SHA is operational metadata, not a secret.
- No credentials, tokens, repository URLs, branch names, or CI variables shall be exposed.
- Jinja autoescaping shall remain enabled.
- Existing authentication and server-side admin role checks shall remain unchanged.

### NFR-COMMIT-02: Reliability

- Missing or malformed metadata shall not prevent `/admin` from rendering.
- The implementation shall not perform filesystem or subprocess Git calls per request.

### NFR-COMMIT-03: Maintainability

- Build metadata shall enter the application through one documented environment variable.
- The displayed short SHA shall be derived in Python and passed explicitly in the admin
  template context.

### NFR-COMMIT-04: Testability

- An example-based test shall verify the commit label and stable selector in rendered HTML.
- A deployment regression test shall verify that GitLab passes `CI_COMMIT_SHA` into the
  Docker build and that the Dockerfile exposes it to the application runtime.

## Acceptance Criteria

1. A production image built for SHA `1234567890abcdef` renders `12345678` in the `/admin`
   navigation bar.
2. A local run without commit metadata renders `unknown`.
3. Non-admin users remain redirected from `/admin`.
4. Other application pages do not receive or display the admin commit label.
5. Unit tests, strict mypy, Bandit, dependency audit, Docker build, and smoke test remain
   green.

## Stage Assessment

- **User Stories**: Skip; the request and acceptance criteria are complete and affect one
  existing administrator workflow.
- **Application Design**: Skip; no new component or service is introduced.
- **Units Generation**: Skip; this is a single web/deployment change.
- **Functional/NFR/Infrastructure Design**: Skip; existing patterns are sufficient.
- **Code Generation**: Execute with a change-specific plan.
- **Build and Test**: Execute.

## Security Compliance

| Rule | Status | Rationale |
|---|---|---|
| SECURITY-03 | Compliant | No secret or PII logging is introduced |
| SECURITY-08 | Compliant | Existing authenticated admin role check remains authoritative |
| SECURITY-09 | Compliant | Fallback is generic and exposes no internal error |
| SECURITY-12 | Compliant | Commit metadata contains no credential and no secret is hardcoded |
| SECURITY-13 | Compliant | SHA improves deployed-artifact traceability |
| SECURITY-01, 02, 04-07, 10, 11, 14, 15 | N/A | No storage, network, dependency, auth, or error-path behavior changes |

No blocking security findings were identified.

## Property-Based Testing Compliance

The change performs a bounded string projection and static template rendering. It adds no
business algorithm, serialization round trip, state machine, or data transformation that
benefits from generated inputs. PBT-01 through PBT-10 are N/A for this change; focused
example-based regression tests provide the appropriate coverage.

## Assumptions

- A short eight-character SHA is sufficiently identifiable in the admin UI.
- The full SHA remains available in the container environment for diagnostics.
- The value embedded at image build time is the source commit represented by that image.
