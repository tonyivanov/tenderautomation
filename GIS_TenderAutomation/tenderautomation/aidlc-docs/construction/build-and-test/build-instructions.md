# Build Instructions — AI Export Integrity EI-1

## Prerequisites

- Python 3.10+ locally; production image runtime is Python 3.12.
- `.venv` populated from `requirements-dev.txt`.
- Docker Engine with Compose and SBOM plugins.
- No live platform, LLM, Telegram, SMTP or production database credentials.
- Synthetic `B2BCENTER_*` and `BIDZAAR_*` values are sufficient.

## Build Steps

1. Install dependencies:

   ```bash
   .venv/bin/python -m pip install -r requirements-dev.txt
   ```

2. Run the Python gates:

   ```bash
   .venv/bin/python -m pytest \
     --hypothesis-seed=20260717 \
     --cov=src --cov-report=term-missing --cov-report=xml \
     --cov-fail-under=60
   .venv/bin/python -m mypy src --ignore-missing-imports
   .venv/bin/python -m bandit -q -r src
   .venv/bin/python -m pip_audit \
     --cache-dir /tmp/tenderautomation-pip-audit \
     -r requirements.txt
   .venv/bin/python -m pip check
   ```

3. Validate production Compose:

   ```bash
   POSTGRES_PASSWORD=ci \
   B2BCENTER_USERNAME=ci B2BCENTER_PASSWORD=ci \
   BIDZAAR_USERNAME=ci BIDZAAR_PASSWORD=ci \
   TENDERAUTOMATION_IMAGE=tenderautomation:ei1-local \
   docker compose --env-file /dev/null \
     -f docker-compose.server.yml config --quiet
   ```

4. Build the production image:

   ```bash
   docker build --pull \
     --build-arg APP_COMMIT_SHA="$(git rev-parse HEAD)" \
     -t tenderautomation:ei1-local .
   ```

5. Generate the SBOM and run smoke:

   ```bash
   docker sbom tenderautomation:ei1-local \
     --quiet --format cyclonedx-json \
     --output /tmp/tenderautomation-ei1-sbom.cdx.json
   scripts/smoke_test.sh tenderautomation:ei1-local
   ```

## Successful Artifacts

- `coverage.xml`.
- Docker image `tenderautomation:ei1-local`.
- CycloneDX SBOM `/tmp/tenderautomation-ei1-sbom.cdx.json`.
- Smoke output `SMOKE_RESULT: passed`.

## Troubleshooting

- Start Docker Desktop if its socket is unavailable.
- Use `--env-file /dev/null` to prevent interpolation from a developer `.env`.
- Give `pip-audit` a writable cache under `/tmp`.
- Set both `DATABASE_URL` and `TEST_POSTGRESQL_URL` to the same isolated
  PostgreSQL database when running the guarded integration suite.
