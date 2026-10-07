# CreditIQ runtime database role audit and cutover

Date: 2026-10-07. Mode remains RESEARCH_ONLY; release_ready=false.

## Previous account

The backend authenticated through the Session Pooler as `postgres.pzknfundavkxzxtrikbq`,
which resolves to PostgreSQL role `postgres`.

| Attribute | Old postgres | New creditiq_runtime |
|---|---|---|
| LOGIN | Yes | Yes |
| SUPERUSER | No | No |
| CREATEDB | Yes | No |
| CREATEROLE | Yes | No |
| REPLICATION | Yes | No |
| BYPASSRLS | Yes | No |
| INHERIT | Yes | No |
| Application table ownership | All 28 + Alembic | None |
| Schema creation | Available as owner/operator | Denied |
| Database creation privilege within current database | Yes | No |
| DELETE / TRUNCATE application data | Available | Denied everywhere |
| Migration metadata access | Read/write | Denied |
| Login connection limit | Platform setting | 20 |

Old memberships: `pg_monitor`, `pg_signal_backend`, `pg_read_all_data`,
`pg_create_subscription`, `anon`, `authenticated`, `service_role`, `authenticator`,
and `supabase_privileged_role`. All except the last were held with ADMIN OPTION.
The new account has **no role memberships**, and no Data API role can switch to it.

The old account could modify schema and roles, read broadly outside normal application
authorization, bypass RLS, and disable immutable-record triggers. An API database
credential compromise therefore exposed administrative capabilities. These privileges
are unnecessary for ordinary request handling.

## Permissions derived from implemented workflows

SELECT + INSERT on these **19 tables** only:

`users`, `user_profiles`, `auth_sessions`, `audit_events`, `loan_applications`,
`application_versions`, `loan_quotes`, `model_versions`, `policy_versions`,
`feature_snapshots`, `scoring_jobs`, `predictions`, `risk_scores`, `decisions`,
`application_history`, `installment_imports`, `installment_schedules`,
`installment_payments`, `installment_analyses`.

Column UPDATE only:

| Table | Columns | Reason |
|---|---|---|
| users | password_hash | Existing password rehash; enables existing FOR UPDATE locking |
| auth_sessions | revoked_at | Rotation, replay handling, logout and revocation |
| loan_applications | workflow_status, current_decision_id | Existing atomic submission finalization |

No access to `data_consents`, `explanations`, `feature_snapshot_sources`, `loan_outcomes`,
`model_deployments`, `outbox_events`, `reports`, `segment_assignments`, `source_snapshots`,
or `alembic_version`: these are not required by current HTTP workflows.
The research/segmentation dashboards read artifact files; they do not need database
write access to model-management or segment-assignment tables.

No DELETE, TRUNCATE, REFERENCES, TRIGGER, table ownership, schema CREATE, role membership,
or automatic future-table grants. UUID defaults require no sequences. Trigger functions
remain installed and enforced without granting direct invocation to the runtime role.

The role receives database CONNECT and public schema USAGE. PostgreSQL's existing
PUBLIC database TEMP privilege still applies, allowing session-local temporary objects;
there is no per-role DENY that can override PUBLIC. Revoking it globally could affect
Supabase platform roles, so shared platform defaults were not changed. This does not
permit creation or modification of persistent application schema objects.

## RLS and authorization

All 29 tables retain ENABLE/FORCE RLS. Added **41 policies**, addressed exclusively to
`creditiq_runtime`: SELECT and INSERT on 19 tables, plus UPDATE on three tables.
These permit the trusted backend to perform its existing cross-user administration
and authentication operations. Policies do not grant SQL object privileges; the
column/table grants above still constrain operations.

This preserves the existing backend tenant-authorization boundary. It does **not** add
per-request user identities to PostgreSQL: the runtime role can see all rows of its
allowed tables. User ownership checks and read-only application-admin permissions remain
in FastAPI. A stolen runtime password still exposes allowed reads/inserts; this change
reduces blast radius rather than making a compromised backend harmless.

No policies or grants were added for `anon`, `authenticated`, or `service_role`.
Their public schema/table/column/function access remains denied. The RLS audit utility
now recognizes the backend-only policies and requires explicit operator credentials.

## SQL and configuration

Exact reviewed security DDL: `services/api/scripts/runtime_role.sql`.
Provisioning: `services/api/scripts/provision_runtime_role.py` executes it transactionally,
sets a securely generated password without printing it, and stages candidate configuration.
No real password appears in the tracked SQL or this report.

Active `services/api/.env` now uses:

```dotenv
CREDITIQ_PG_USER=creditiq_runtime.pzknfundavkxzxtrikbq
CREDITIQ_PG_PASSWORD=<generated-private-runtime-password>
```

The existing Session Pooler host, port 5432, database postgres, TLS verify-full, certificate,
pool size and application settings are unchanged. No migration credential is loaded into
the runtime .env. A private operator URL is retained in the ignored
`services/api/.postgres/supabase-operator.env`; previous configuration and rollback evidence
are also ignored. **Do not package or deploy .postgres, private backups, or operator secrets
with the API.** Supply operator credentials only to separate migration/security jobs.

The Supabase custom-role pooler username format is documented in
[Supabase connection guidance](https://supabase.com/docs/guides/database/connecting-to-postgres).

No API code, authentication behavior, model artifacts, business calculations or Alembic
revision changed. Revision remains `20261003_0003`. No user-facing API server was listening
on port 8000 during cutover; the next IDE launch reads the updated .env. Already-running
processes elsewhere must restart to discard old operator connections.

## Validation

- New account authenticated against the real Supabase Session Pooler.
- **42 smoke checks passed** using the restricted account and staging startup checks:
  registration, login, current user, sessions, refresh, session revocation, logout;
  real Lite scoring, atomic application creation, idempotent replay, retrieval/history;
  installment import/timeline, borrowing planner, cross-user denial, admin denial for
  ordinary users, read-only admin endpoints, research and segmentation artifact endpoints.
- Ten forbidden SQL operations denied with SQLSTATE 42501: CREATE TABLE, disable RLS,
  TRUNCATE, DELETE, update user role, modify prediction, read Alembic metadata, read unused
  outbox, SET ROLE postgres, SET ROLE service_role.
- HTTP smoke fixture transactions used an outer rollback; all 312 pre-existing application
  rows and the Alembic row have unchanged fingerprints. No test users/sessions persisted.
- Existing-user password hashes and sessions were preserved; the smoke authenticated new
  rollback-only users, not existing users whose plaintext passwords were unavailable.
- Standalone smoke utility: `services/api/scripts/validate_runtime_role.py`.
- Full regression and final active-configuration checks: recorded below after completion.

## Operational risks remaining

Deploy with the restricted credentials only; never restore postgres as a silent fallback.
Future features/migrations must explicitly review grants and RLS policies. Database account
connection limit is 20; retain the current bounded application pool and budget workers.
Configure production HTTPS/cookies and finish the outstanding Data API control-plane/keyed
HTTP check and deployment security verification. This cutover alone does not authorize
production lending or set production_ready=true.

## Post-cutover verification

Fresh Settings() reads the restricted account from the active .env. A real connection
reported current_user=creditiq_runtime and all administrative flags false; zero public
objects are owned by it. Fresh FastAPI startup succeeded and health/live and health/ready
both returned 200. No API role (including authenticator) is a member of creditiq_runtime.
The final role-switched Data API denial checks still passed for all 29 tables x 3 roles.
Evidence: ignored .postgres/runtime-active-verification.json, runtime-provisioning.json,
and runtime-validation.json. No credentials are included in these JSON reports.

### Effective table privileges

Table-level UPDATE is denied everywhere; the four column grants listed above are the
only update exceptions. DELETE/TRUNCATE denied on every table.

| Table | SELECT | INSERT | UPDATE columns |
|---|---|---|---|
| alembic_version | No | No | None |
| application_history | Yes | Yes | None |
| application_versions | Yes | Yes | None |
| audit_events | Yes | Yes | None |
| auth_sessions | Yes | Yes | revoked_at |
| data_consents | No | No | None |
| decisions | Yes | Yes | None |
| explanations | No | No | None |
| feature_snapshot_sources | No | No | None |
| feature_snapshots | Yes | Yes | None |
| installment_analyses | Yes | Yes | None |
| installment_imports | Yes | Yes | None |
| installment_payments | Yes | Yes | None |
| installment_schedules | Yes | Yes | None |
| loan_applications | Yes | Yes | current_decision_id, workflow_status |
| loan_outcomes | No | No | None |
| loan_quotes | Yes | Yes | None |
| model_deployments | No | No | None |
| model_versions | Yes | Yes | None |
| outbox_events | No | No | None |
| policy_versions | Yes | Yes | None |
| predictions | Yes | Yes | None |
| reports | No | No | None |
| risk_scores | Yes | Yes | None |
| scoring_jobs | Yes | Yes | None |
| segment_assignments | No | No | None |
| source_snapshots | No | No | None |
| user_profiles | Yes | Yes | None |
| users | Yes | Yes | password_hash |

## Final regression results

- Full isolated regression run: 152 passed, 2 failed, 1 existing Starlette/httpx warning.
- Both failures were secure-cookie unit fixtures inheriting the developer's COOKIE_SECURE=false.
  The test helper now explicitly selects cookie_secure=True; no runtime setting or behavior changed.
- Targeted rerun of all hardening tests and the new runtime SQL test: **16 passed**, one
  existing deprecation warning. Thus **154 distinct backend tests passed across the full
  run and targeted rerun**, with no unresolved test failures. The full suite was not run
  a fourth time after this fixture-only change.
- Earlier attempts also exposed local-test configuration omissions (Supabase .env inherited
  by a localhost assertion, and a legacy backup missing DB_HOSTING). Tests subsequently
  used explicit local hosting/direct/SSL-disabled overrides only in the child process.
  Active Supabase configuration was never reverted for testing.
- Exact deployed SQL regression passes: column grants, RLS insert/update, forbidden writes,
  absent migration access, and all 41 policies; all fixture DDL/data rolled back locally.
- Python compilation and git diff whitespace checks passed. No frontend/ML files changed
  in this task, and no model training occurred.

### Files for this change

Created: runtime_role.sql, provision_runtime_role.py, validate_runtime_role.py under
services/api/scripts; tests/test_runtime_privileges.py; this report.
Modified: security audit utility; tests/test_hardening.py fixture; active ignored .env;
RLS_AUDIT_REPORT.md; ../Deployment/PRODUCTION_READINESS_REPORT.md; ../Deployment/DEPLOYMENT_CHECKLIST.md;
../Deployment/ENVIRONMENT_VARIABLES_REFERENCE.md; project progress, backend TODO and changelog.
Private provisioning, backup and validation evidence is kept under ignored .postgres.

Final independence check: local PostgreSQL stopped; fresh FastAPI startup used creditiq_runtime on Supabase and /health/ready returned 200.
