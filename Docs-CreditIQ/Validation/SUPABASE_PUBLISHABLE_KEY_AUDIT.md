# Supabase publishable-key and Data API repository audit

Date: 2026-10-07. **Repository integration audit: PASS.**

CreditIQ does not require a Supabase publishable (formerly anon) key.

| Check | Result | Evidence |
|---|---|---|
| `@supabase/supabase-js` dependency | None found | `apps/web/package.json`, `apps/web/package-lock.json` |
| `createClient(...)` Supabase client initialization | None found | Application/deployment source search |
| `SUPABASE_URL` configuration | None found | Source, templates, and ignored runtime env variable names |
| `SUPABASE_ANON_KEY` / publishable-key configuration | None found | Source, manifests, templates, and ignored env variable names |
| Calls to `/rest/v1` | None found | Application and deployment source search |
| Supabase Auth integration | None found | Auth is CreditIQ's FastAPI JWT/cookie/session implementation |
| Supabase Storage integration | None found | No SDK, client, or Storage API use found |

Supabase database configuration uses `CREDITIQ_DB_HOSTING`, `CREDITIQ_PG_*`, TLS, and
pool settings. SQLAlchemy creates the `postgresql+psycopg` URL in
`services/api/app/core/config.py:101` and the API engine in `services/api/app/db/session.py:16`.
Alembic uses the PostgreSQL operator URL in `services/api/migrations/env.py:14,30`.
The frontend sends same-origin requests to FastAPI through the Next rewrite in
`apps/web/next.config.ts`.

Therefore **CreditIQ's Data API/key dependency verification is complete**: the application
has no client flow that could require a publishable key, and a keyed REST test is not
needed to validate its features. The separate database security audit verified the
`anon`, `authenticated`, and `service_role` roles cannot access the 29 public tables;
see `RLS_AUDIT_REPORT.md`.

This source audit does not inspect the Supabase Dashboard's exposed-schema toggle.
`public` may remain listed as exposed at the API gateway, while the database ACL/RLS
checks deny these roles access to CreditIQ data. No claim is made that the gateway is
disabled or that `public` is absent from that control-plane setting.

## Conclusion

- Publishable key needed by CreditIQ: **No**.
- Database connectivity: **PostgreSQL protocol through Supavisor Session Pooler**, using
  the restricted `creditiq_runtime` role and `psycopg`.
- Supabase Data API, Auth, or Storage used by the application: **No**.
- Application Data API/key dependency verification: **Complete**.
- Dashboard exposed-schema configuration: **Not inspected by this repository audit**.
