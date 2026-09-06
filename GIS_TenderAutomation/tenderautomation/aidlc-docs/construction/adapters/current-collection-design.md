# Current Collection Design — Post-Rebase Amendment

Status: approved by user follow-up on 2026-07-17. This amendment supersedes the
legacy single-transport and credential-based collection sections in the original Unit 2 design.

## B2B-Center: two retained collection transports

`B2BCenterScraper.fetch_new()` executes the transports listed in
`descriptor.extra.fetch_modes`; the default is `[endpoint, playwright]`.

1. `endpoint` uses `httpx.AsyncClient`, saved B2B cookies, and the recommendations
   feed at `/market/`. It is capped by `endpoint_max_pages`.
2. `playwright` performs query-based search from `queries.yaml`, handles CAPTCHA
   retry, and injects saved cookies into the browser context.
3. Results are deduplicated by stable `external_id`. A failure in one transport does
   not discard results from the other; collection fails only if every configured
   transport raises.

Configuration supports endpoint-only, Playwright-only, or both modes without code changes.

## Bidzaar: public collection, private analysis

- Collection uses the public async integrator endpoint. It needs no user credentials.
- The API client clamps `FromDate` to the supported 13-day window, filters rows at or
  before the exact `since` boundary, removes expired rows, normalizes timestamps to UTC,
  and deduplicates UUIDs extracted from `link`.
- V3 deep analysis of private attachments is a separate opt-in path. An operator runs
  `scripts/bidzaar_login.py`, which writes ignored session/token files under `data/`.
  Deep analysis reads the cache and rejects missing or expired tokens without logging them.

## Tests and failure behavior

- Unit tests cover both B2B transports, deduplication, partial-source failure, and mode validation.
- Bidzaar tests cover async collection, schema mapping, date-window clamping, exact
  incremental boundary, expiry filtering, unknown deadlines, and private-token expiry.
- HTTP failures include only exception types in structured logs; credentials and tokens
  are never logged.
