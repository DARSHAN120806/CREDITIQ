> Current-state follow-up: the backend now uses `creditiq_runtime`, with 41 policies
> restricted to that backend role. Data API roles remain denied. The original zero-policy
> audit below is a historical checkpoint; see `RUNTIME_DATABASE_ROLE_REPORT.md` for current
> backend grants. The security utility now requires a separately supplied operator URL.

# Supabase RLS and exposure audit

Date: 2026-10-07. Database lockdown **APPLIED AND VERIFIED**.
`mode=RESEARCH_ONLY`; `release_ready=false`; `production_ready=false`.

## Access design

All 28 application tables contain private application, authentication, analytics,
or operational data. All require RLS defense in depth. None is intended for direct
Supabase Data API access. CreditIQ uses FastAPI authorization and its own JWT/session
system; Supabase `authenticated` is not a CreditIQ user identity.

Accordingly, no row-access policies were created. RLS with no policies denies rows
to ordinary roles. Do not add `auth.uid()` policies or blanket `USING (true)` policies
for API roles. A future restricted backend role needs explicitly scoped grants and
backend-only policies before replacing the current operator account.

## Findings and changes

Before: 28/28 application tables had RLS disabled, no policies, and broad grants
to `anon`, `authenticated`, and `service_role`. Public schema USAGE and trigger-function
EXECUTE were also available to these roles.

Applied in one transaction:

- ENABLE and FORCE ROW LEVEL SECURITY on all 28 tables and `alembic_version`.
- Revoke all table and column privileges from PUBLIC and the three API roles.
- Revoke public schema privileges from PUBLIC and the three API roles.
- Revoke EXECUTE on the three public trigger functions and all public sequence grants.
- Revoke postgres-created public table, sequence, and function default grants to API roles.
- Revoke global default PUBLIC EXECUTE for future postgres-created functions: PostgreSQL
  schema-specific revocation cannot cancel that global default. Existing other schemas
  and their grants were not changed.
- Notify PostgREST to reload its schema cache.

No application code, authentication logic, model files, records, or Alembic revision changed.
Security DDL is recorded in an operator script, not a new Alembic revision.

## Effective permissions after commit

| Role | Public schema USAGE / CREATE | Table SELECT / INSERT / UPDATE / DELETE / TRUNCATE / REFERENCES / TRIGGER | Column grants | Public function EXECUTE | BYPASSRLS |
|---|---|---|---|---|---|
| anon | Denied / denied | All denied, all 29 tables | None | Denied, all 3 functions | No |
| authenticated | Denied / denied | All denied, all 29 tables | None | Denied, all 3 functions | No |
| service_role | Denied / denied | All denied, all 29 tables | None | Denied, all 3 functions | Yes, platform attribute retained |

`service_role` bypasses RLS but does **not** bypass PostgreSQL object privileges.
It therefore has no direct access to these application tables. Do not later restore
its schema/table grants assuming RLS will protect the rows.

The existing backend connects as `postgres`, owns these tables, and has BYPASSRLS.
Backend database reads still work; a zero-row UPDATE permission probe succeeded.
This maintains current behavior, but this elevated runtime role remains a deployment
blocker. RLS does not replace backend ownership/RBAC checks for that connection.

## Validation

- Real role-switched SELECT attempts denied with SQLSTATE 42501: 29 tables x 3 roles,
  tested within the change transaction and again through a new connection after commit.
- Catalog checks show no effective table or column grants for those roles.
- All 3 public functions deny EXECUTE to all 3 roles.
- Defense-in-depth test temporarily granted schema USAGE and table SELECT to anon
  and authenticated inside savepoints: each saw **zero rows across all 29 tables**.
  Both sets of temporary grants were rolled back; no permissive policies were added.
- All **312 application rows** have identical before/after table fingerprints.
- `alembic_version` still contains **20261003_0003**, with an unchanged fingerprint.
- No application writes or data migrations performed. No model inference/retraining.
- Existing full backend/browser suites were not rerun for this database-only operation;
  previous hardening results were 153 backend and 38 browser tests passed.

Private evidence, containing counts/ACLs/hashes rather than customer record contents:
`services/api/.postgres/rls-preflight.json`, `rls-applied-verification.json`,
and `rls-extra-verification.json`.

## Data API exposure: exact scope of confirmation

The repository audit found no Supabase SDK, publishable-key setting, `/rest/v1`, Auth,
or Storage integration. CreditIQ does not need a publishable key, and a keyed application
REST test is not applicable. The prior request without an API key returned **401**. The
Dashboard's exposed-schema configuration is not recorded in PostgreSQL, so **public may
still be listed as an exposed schema**. The SQL role controls remain the verified data
protection.

Even if public remains listed, the verified roles cannot access CreditIQ's public
tables or functions under the current grants. Schema listing and data accessibility
are separate facts. No claim is made that the Data API itself has been disabled.

CreditIQ's repository Data API dependency/key audit is complete. If a guarantee that
the gateway does not expose `public` is required, inspect the Dashboard's exposed-schema
setting separately. The backend needs no Supabase API keys.

Platform-owned `supabase_admin` public default grants remain; postgres is not a member
of that role. The public-schema privilege barrier denies API access even if such a
platform-created object gets table grants. Re-audit after Dashboard-created objects,
extensions, schema grants, role membership changes, or migrations. New table creators
must explicitly enable RLS; default privileges do not enable it automatically.

## Reproducibility and recovery

Operator utility: `services/api/scripts/secure_supabase_access.py`. From services/api,
set `$env:PYTHONPATH='.'`, then run the existing venv Python with that script,
`--output <new-private-evidence-path>` for read-only audit, or add `--apply` for the
authorized lockdown. It refuses unexpected inventory, policies, functions or revisions.
Use operator credentials privately; do not grant the runtime DDL permission to run it.

The apply transaction locks the tables briefly with a five-second lock timeout,
checks data fingerprints, and rolls back on pre-commit validation failure. Reapplying
is safe for this exact inventory. If the application later needs a restricted runtime
role, grant that named role only the required access and policies. Do not recover by
restoring broad anon/authenticated/service_role grants. Pre-change ACL evidence is
retained for controlled investigation.

References: [Supabase API security](https://supabase.com/docs/guides/api/securing-your-api)
describes grants and RLS as separate protections;
[PostgreSQL row security](https://www.postgresql.org/docs/current/ddl-rowsecurity.html)
documents default-deny policies and BYPASSRLS behavior.

## Table-by-table inventory

Every row below has ENABLE + FORCE RLS, zero policies, and no access for the three
Data API roles. Row counts and fingerprints are unchanged.

| Table | Rows before | Rows after | RLS / FORCE | Fingerprint |
|---|---:|---:|---|---|
| alembic_version | 1 | 1 | Enabled / enforced | Match |
| application_history | 8 | 8 | Enabled / enforced | Match |
| application_versions | 8 | 8 | Enabled / enforced | Match |
| audit_events | 135 | 135 | Enabled / enforced | Match |
| auth_sessions | 29 | 29 | Enabled / enforced | Match |
| data_consents | 0 | 0 | Enabled / enforced | Match |
| decisions | 8 | 8 | Enabled / enforced | Match |
| explanations | 0 | 0 | Enabled / enforced | Match |
| feature_snapshot_sources | 0 | 0 | Enabled / enforced | Match |
| feature_snapshots | 8 | 8 | Enabled / enforced | Match |
| installment_analyses | 2 | 2 | Enabled / enforced | Match |
| installment_imports | 2 | 2 | Enabled / enforced | Match |
| installment_payments | 42 | 42 | Enabled / enforced | Match |
| installment_schedules | 24 | 24 | Enabled / enforced | Match |
| loan_applications | 8 | 8 | Enabled / enforced | Match |
| loan_outcomes | 0 | 0 | Enabled / enforced | Match |
| loan_quotes | 8 | 8 | Enabled / enforced | Match |
| model_deployments | 0 | 0 | Enabled / enforced | Match |
| model_versions | 1 | 1 | Enabled / enforced | Match |
| outbox_events | 0 | 0 | Enabled / enforced | Match |
| policy_versions | 1 | 1 | Enabled / enforced | Match |
| predictions | 8 | 8 | Enabled / enforced | Match |
| reports | 0 | 0 | Enabled / enforced | Match |
| risk_scores | 8 | 8 | Enabled / enforced | Match |
| scoring_jobs | 8 | 8 | Enabled / enforced | Match |
| segment_assignments | 0 | 0 | Enabled / enforced | Match |
| source_snapshots | 0 | 0 | Enabled / enforced | Match |
| user_profiles | 2 | 2 | Enabled / enforced | Match |
| users | 2 | 2 | Enabled / enforced | Match |
