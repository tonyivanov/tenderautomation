# Admin Commit ID - Implementation Summary

## Outcome

The authenticated `/admin` page now displays the deployed source revision in its top
navigation bar as `commit <short-sha>`. The label has the stable selector
`data-testid="admin-commit-id"` and is omitted from pages whose template context does
not define `commit_id`.

## Modified Runtime Files

- `src/core/config.py` defines `app_commit_sha` with the safe default `unknown`.
- `src/web/routers/admin_router.py` validates the configured value, reduces a valid
  hexadecimal revision to eight lowercase characters, and passes it only to the admin
  template context.
- `src/web/templates/base.html` renders the conditional top-bar label.
- `Dockerfile` accepts `APP_COMMIT_SHA` as a build argument and persists it as runtime
  metadata in the image.
- `.gitlab-ci.yml` passes GitLab's predefined `CI_COMMIT_SHA` into the production image
  build.
- `scripts/smoke_check.py` verifies the authenticated `/admin` response and the expected
  label value.
- `tests/unit/web/test_merge_readiness.py` covers normalization, conditional rendering,
  and the GitLab/Docker metadata contract.

## Runtime Contract and Fallback

The GitLab image build supplies the full revision through `APP_COMMIT_SHA`. At runtime,
the web layer accepts only 8 to 64 hexadecimal characters and displays the first eight
in lowercase. Missing, short, or malformed values render as `unknown`. The request path
does not invoke Git or read repository metadata, so the behavior remains deterministic
inside immutable production images and in local development.

## Security Baseline Assessment

- **SECURITY-03 / SECURITY-12**: no environment dump, secret logging, or additional
  credential handling was introduced; only a validated hexadecimal revision is shown.
- **SECURITY-08**: the existing server-side admin role check remains unchanged.
- **SECURITY-09**: malformed metadata is replaced with the generic value `unknown`.
- **SECURITY-13**: the displayed revision improves deployment traceability.
- Other security baseline controls are not affected by this static metadata change.

No blocking security finding was identified.

## Property-Based Testing Assessment

Property-based tests are not applicable to this unit. The new logic is a small,
finite validation boundary without round trips, state transitions, idempotent effects,
or a reference algorithm. Parameterized examples cover the accepted and rejected input
classes directly; the repository-wide Hypothesis suite remains part of Build and Test.
