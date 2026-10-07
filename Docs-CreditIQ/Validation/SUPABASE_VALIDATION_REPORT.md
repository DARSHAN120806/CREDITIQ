# Supabase hosting migration validation

Date: 2026-10-07. **Session Pooler transport verified; authentication and migration remain pending.**
`mode=RESEARCH_ONLY`, `release_ready=false`.

## Current database verified

The active ignored `services/api/.env` now selects Supabase Session Pooler at
`aws-0-ap-south-1.pooler.supabase.com:5432`, database `postgres`, username
`postgres.pzknfundavkxzxtrikbq`, with TLS `verify-full`. Its configured CA file exists.
No backend was listening on port 8000 during this audit. Previous local settings were preserved in ignored
`.postgres/local-runtime.env.backup`; JWT, cookie and authentication settings were kept.
The populated `supabase.env.example` was sanitized back to placeholders.

The local source was started temporarily and inspected read-only, then stopped. It is
PostgreSQL **18.6**, revision **20261003_0003**, with **28 application tables** plus
`alembic_version`, database size **10,557,119 bytes**, and **280 application rows**.
Counts include 2 users, 29 auth sessions, 8 applications, 8 predictions, 2 installment
imports and 42 installment payments. No local records were copied.

The configured DNS resolver `192.168.0.1` timed out. Public DNS resolved the supplied
Session Pooler to two IPv4 addresses. Both accepted TCP on port 5432 and completed a
PostgreSQL SSLRequest followed by TLS 1.3 with certificate chain and hostname verification.
This verifies network transport only: no PostgreSQL password was sent and no SQLAlchemy
login, query, migration or remote schema check has succeeded. The direct endpoint remains
IPv6-only from public DNS and is not routable from this network. Active mode is `session`.

**Rotate the Supabase database password in the Dashboard before any authentication retry.**
The previous password appeared in diagnostic output. The ignored active `.env` still needs
the rotated password entered locally; do not send it in chat. The populated example file
was sanitized back to placeholders. Never commit `.env` or its private rollback backup.

## Changes delivered

| File | Change |
|---|---|
| `services/api/app/core/config.py` | Backward-compatible hosting/connection modes, CA path and separate secret migration URL. Supabase URLs require TLS. |
| `services/api/app/db/session.py` | Disable psycopg automatic prepared statements only for transaction pooling. Existing sessions/transactions/pool defaults preserved. |
| `services/api/migrations/env.py` | Use the independent operator URL for online/offline Alembic; preserve supplied connections and NullPool. Hide SQL parameters. |
| `services/api/.env.example` | Document optional settings; keep local defaults. |
| `services/api/supabase.env.example` | New placeholder-only DB environment template. |
| `services/api/scripts/database_snapshot.py` | New read-only, repeatable-read count/content-hash verification for all 28 tables; UTC serialization, streaming reads and exclusive output creation. |
| `services/api/tests/test_supabase_config.py` | 12 new connection/TLS/secret/mode tests, with no network access. |
| `services/api/tests/test_database.py` | New real-PostgreSQL snapshot repeatability test. |
| `../Architecture/SUPABASE_MIGRATION_PLAN.md` | Audit, setup, connection roles, env variables, export/import commands, permissions, deployment checklist and rollback. |
| `Docs-CreditIQ/Research/PROJECT_PROGRESS.md` | Record preparation completed and live migration pending. |
| `Docs-CreditIQ/Architecture/BACKEND_TODO.md` | Track target provisioning, rehearsal, cutover and live checks. |
| `Docs-CreditIQ/CHANGELOG.md` | Record exact scope and preservation boundaries. |
| `SUPABASE_VALIDATION_REPORT.md` | This validation record. |

No dependencies were added. No authentication implementation, routes/API contracts,
domain models, schema revisions, prediction behavior or trained artifacts were edited.
No Supabase Auth or Supabase SDK was introduced. No password was sent during pooler
transport checks; SQLAlchemy authentication has not been attempted since those checks.
The pre-existing edit to `apps/web/app/globals.css` was preserved.

## Backend validation

All **137 distinct backend tests passed across complementary runs**:

1. Full suite with `CREDITIQ_TEST_POSTGRES=1`: **128 passed**, eight fixture setup errors.
   The errors were Windows permission denial for the existing system pytest temporary
   directory, not failed application assertions. One existing Starlette/httpx deprecation warning.
2. Reran `tests/test_model_research.py` and the new snapshot integration test with
   `--basetemp=.postgres/pytest-supabase-20261006`: **10 passed**. This covers all eight
   setup errors, one already-passing research test, and the newly added snapshot test.
3. After narrowing the migration URL parser's exception handling, reran the new
   connection configuration module: **12 passed** (included in the distinct total).
4. Extra transaction-mode client check: registration/login/secret storage, refresh
   rotation and logout: **3 passed**, 31 deselected, same existing warning. This tests
   `prepare_threshold=None` against local PostgreSQL, **not** an actual Supavisor pooler.

The full suite exercises JWT, password hashing, registration, cookies, CSRF, refresh-token
replay/races, session ownership, RBAC, database constraints/migration round trips, owned
applications, model predictions, planner, installment calculations and research endpoints.
Tests use only `creditiq_migration_test`; their fixture cleanup must never be pointed at
a populated Supabase database.

Reproduce locally from `services/api`, with the isolated local cluster running:

```powershell
$env:CREDITIQ_TEST_POSTGRES = '1'
.\.venv\Scripts\python.exe -m pytest -q --basetemp=.postgres/pytest-supabase-next
```

Choose a new, workspace-contained temporary directory for each independent run.

## Frontend validation

- `npm.cmd run typecheck`: **passed**.
- `CREDITIQ_WEB_DIST_DIR=.next-installment-test; npm.cmd run build`: **passed**, including
  compilation, type checks, static page generation and build traces.
- Browser tests use a separate API on port 8002, frontend on port 3012 and the disposable
  local test database. No customer accounts were registered in the user's actual database.
- Full Playwright suite: **30 passed, 8 failed** in 12.3 minutes. Focused retry:
  **1 passed, 1 failed**. Across runs, 31 of 38 tests passed; seven still fail.
- Five failures are assertions expecting light-theme colors: one amber-banner background
  and four disclaimer text colors. Actual dark-theme colors differ; all four disclaimer
  font-size assertions (at least 12px) pass before the color assertion fails.
- The installment demonstration page fails a mobile horizontal-overflow check.
- The personal installment workflow initially timed out waiting for registration;
  its focused retry **passed**, including split payments, saved analysis and dashboard.
- The application workflow initially timed out waiting for navigation after a successful
  `201` response. On retry it passed registration, login, real prediction, result display,
  access-cookie removal/refresh, history and dashboard checks, then failed the mobile
  dashboard horizontal-overflow assertion. Later profile/guard/logout steps in that
  browser test were not reached; backend tests separately cover those auth controls.
- Admin read-only views, research dashboards, planner and financial calculation checks
  passed. Frontend validation is **not fully green**. No frontend changes or test-assertion
  edits were made to hide these results. Follow up on dark-theme assertions and mobile
  overflow as a separate UI task; these checks do not prove Supabase compatibility.
- Existing browser artifacts are under `apps/web/test-results/`; retry traces are under
  `apps/web/test-results/supabase-retry/`. Test-server listeners were stopped afterward;
  generated Next configuration changes were restored. User ports 3000/8000 were untouched.
- Existing Node `NO_COLOR` / `FORCE_COLOR` environment warnings appeared during tests.

## Pending Supabase gates

- Rotate the database password, then update the ignored active `.env` locally. Do not share it in chat.
- Test SQLAlchemy connectivity and verify remote PostgreSQL identity/revision read-only over the configured Session Pooler.
- Confirm target PostgreSQL version and rehearse compatibility from PostgreSQL 18.6.
- Verify connection limits and restricted runtime permissions.
- Operator and restricted runtime roles; effective grants and disabled Data API verification.
- Schema deployment and export/import on the actual target. The runbook commands have not
  been executed against Supabase. Do not treat documentation as a completed transfer.
- Source/target snapshot digest and row-count comparisons, FK/index/trigger verification,
  and preserved users, hashes, refresh sessions and prediction records.
- Real target register/login/JWT/refresh/logout and browser workflows.
- Controlled write freeze, secret provisioning, worker cutover, monitoring and rollback rehearsal.

## Source data and downtime estimate

The local database is small: **10,557,119 bytes** and **280 application rows**. Once
the pooler connects and target-version compatibility passes, allow approximately
**15–30 minutes of write downtime** for a final write freeze, export, import, table/hash
checks and auth smoke tests. This is an estimate, not a measured run; a failed rehearsal
or incompatibility adds time. Keep the local source intact and authoritative until the
target checks pass.

**Release decision:** active settings point at Supabase, but this network cannot reach the
direct IPv6 endpoint. No Alembic command ran; Supabase revision, tables and rows remain
unverified. No data was copied; local remains authoritative. Rotate the database password
and obtain the exact IPv4 Session Pooler settings before continuing. Keep existing JWT
settings and verify target-version compatibility before importing.
