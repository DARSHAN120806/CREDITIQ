# CreditIQ: PostgreSQL hosting migration to Supabase

Prepared 2026-10-06; transport update 2026-10-07. **No Supabase migration has run.**
Mode remains `RESEARCH_ONLY`, `release_ready=false`. The supplied IPv4 Session Pooler
passes DNS, TCP and TLS certificate/hostname verification. SQLAlchemy authentication is
pending password rotation and local secret update. No database writes were made.

## 1. Configuration audit and scope

The current backend uses synchronous SQLAlchemy with psycopg 3. Runtime connections
are constructed by `Settings.database_url` from `CREDITIQ_PG_*`; there is no generic
`DATABASE_URL` consumer. `app/db/session.py` creates a bounded, pre-ping connection
pool, and yields request-scoped sessions. Services continue to own transaction boundaries.
Alembic uses `migrations/env.py`, not a password in `alembic.ini`.

The local cluster is PostgreSQL 18.6. There are **28 application tables**, plus
`alembic_version`. The expected head is **20261003_0003**. Reuse the three existing
migrations, constraints, immutable-record triggers and indexes. No new revision is needed.

Authentication remains CreditIQ-owned: password hashes in `users`, refresh-token
digests/session state in `auth_sessions`, JWT signing configuration outside the DB,
existing HttpOnly cookies, CSRF and RBAC. Supabase supplies PostgreSQL hosting only.
Do not create Supabase Auth users, import into `auth.users`, install its client SDK,
or use anon/service-role API keys. ML artifacts stay on the existing filesystem.

## 2. Create and prepare the destination

1. Create a dedicated Supabase project in the chosen region. Save its operator
   password privately. Do not share this project with unrelated applications.
2. Disable the **Data API** before creating CreditIQ tables. The backend connects
   directly to PostgreSQL and does not need it. Public-schema defaults can otherwise
   expose tables via Supabase roles. Keep it disabled after cutover.
3. Retrieve connection parameters and the provider CA certificate from the project's
   Connect/database settings. Determine target PostgreSQL version with `SHOW server_version`.
4. Use a direct connection for Alembic/export/import. If the operator has IPv4 only,
   use the Supavisor **session** pooler. Never use the transaction pooler for migration tools.
5. The source is PostgreSQL 18. A PostgreSQL 18 `pg_dump` is required to read it.
   **A target older than PostgreSQL 18 is a compatibility gate, not an automatic pass.**
   PostgreSQL does not guarantee restore into older major versions. Rehearse the entire
   migration on a disposable target of that exact version; have an operator review
   generated SQL, types and settings (for example `transaction_timeout` is unsupported
   before PostgreSQL 17). Do not silently strip errors or proceed with partial imports.
6. Check disk/quota, connection limits, network reachability and certificate hostname
   verification. Allow migration tools from an authorized operator machine only.

Official references: [connections](https://supabase.com/docs/guides/database/connecting-to-postgres),
[migration guide](https://supabase.com/docs/guides/platform/migrating-to-supabase/postgres),
[Data API security](https://supabase.com/docs/guides/api/securing-your-api),
[PostgreSQL pg_dump](https://www.postgresql.org/docs/18/app-pgdump.html).

## 3. Environment variables and connection roles

Use `services/api/supabase.env.example` as a **template**, merging only DB settings
into a private environment. Do not replace the existing `.env` wholesale.

| Variable | Value / purpose |
|---|---|
| `CREDITIQ_DB_HOSTING` | `supabase`; enforces encrypted runtime and migration URLs |
| `CREDITIQ_PG_HOST` | `<pooler-host>` from project Connect panel |
| `CREDITIQ_PG_PORT` | `<session-or-transaction-port>` from Connect panel |
| `CREDITIQ_PG_DATABASE` | `<target-database>` |
| `CREDITIQ_PG_USER` | `<restricted-runtime-pooler-username>`; use provider-required project suffix |
| `CREDITIQ_PG_PASSWORD` | `<restricted-runtime-role-password>`; raw value, not URI-encoded |
| `CREDITIQ_PG_CONNECTION_MODE` | `session` recommended initially; `transaction` supported |
| `CREDITIQ_PG_SSLMODE` | `verify-full` recommended; `require` encrypts without equivalent hostname verification |
| `CREDITIQ_PG_SSLROOTCERT` | `<absolute-provider-CA-path>` for verified TLS |
| `CREDITIQ_DB_POOL_SIZE` | Initially `5`, adjust to available connection budget |
| `CREDITIQ_DB_MAX_OVERFLOW` | Initially `0`; multiply total pool budget by all API workers |
| `CREDITIQ_MIGRATION_DATABASE_URL` | **Operator only**: `<direct-or-session-SQLAlchemy-URL>` |
| `CREDITIQ_MODE` / `CREDITIQ_RELEASE_READY` | `RESEARCH_ONLY` / `false` |

The migration URL uses the `postgresql+psycopg` driver with username, password, host,
port, database and its own `sslmode=verify-full` / `sslrootcert` query options. Build
it using SQLAlchemy `URL.create(...).render_as_string(hide_password=False)` in a private
operator process or a secret manager. URL credentials/query paths must be correctly
encoded. Never print the result or put it in command history, code or `alembic.ini`.
Runtime TLS fields do not automatically modify an explicit migration URL.

Migration URLs use an elevated operator role; runtime connections use a separate
restricted login. Create the runtime login using the provider's supported role
administration workflow and a privately supplied password. The API must never run as
`postgres` or the migration owner. Keep the operator URL out of the API environment.

Copy the existing JWT secret, issuer/audience and token lifetimes **unchanged** through
the deployment secret store. Keep the same frontend/backend origins and cookie settings
when only moving the database. If web hosting also changes later, configure HTTPS,
Secure cookies and explicit origins separately; cookies cannot move across domains.

Transaction pooling disables psycopg automatic prepared statements in the engine.
Direct/session mode retains existing driver defaults. SQLAlchemy sessions and service
transactions are unchanged; current advisory locks are transaction scoped.
See [prepared statements](https://supabase.com/docs/guides/troubleshooting/disabling-prepared-statements-qL8lEL)
and [pool limits](https://supabase.com/docs/guides/database/connecting-to-postgres/pooling-and-limits).

## 4. Export source schema and data (operator PowerShell)

Run from `services/api`. Commands below are templates, not an instruction to execute
against an arbitrary populated database. First rehearse on disposable source/target
copies. During final export **stop all source writes**, including auth/session refresh,
background jobs and admin tools; leave writes stopped through verification/cutover.
Per-table exports below are consistent only under this write freeze.

Create an access-restricted backup folder outside the repository. Dumps include password
hashes, refresh digests and applicant information: encrypt storage, restrict Windows ACLs,
do not upload to Git or public artifacts, and define retention/deletion procedures.

Set native PostgreSQL tool variables privately. `PGPASSFILE` points to a protected
libpq password file; do not put passwords on the command line. Source values describe
the local source, not the target. `CREDITIQ_MIGRATION_DATABASE_URL` must identify that
same source with an owner/read-capable operator role for the snapshot command.

```powershell
$env:PGHOST = '<source-host>'
$env:PGPORT = '<source-port>'
$env:PGDATABASE = '<source-database>'
$env:PGUSER = '<source-operator-role>'
$env:PGPASSFILE = '<absolute-protected-password-file>'
$env:PGSSLMODE = '<source-sslmode>'
$pgBin = '<PostgreSQL-18-bin-directory>'
$backup = '<new-private-backup-directory>'
New-Item -ItemType Directory -Path $backup -ErrorAction Stop | Out-Null
$tables = @(& .\.venv\Scripts\python.exe -c 'from app.db.base import Base; from app.db import models; print("\n".join(t.name for t in Base.metadata.sorted_tables))')
if ($LASTEXITCODE -ne 0 -or $tables.Count -ne 28) { throw 'Unexpected application table inventory' }
& "$pgBin\pg_dump.exe" --no-password --quote-all-identifiers --schema-only --schema=public --no-owner --no-privileges --file="$backup\source-schema.sql"
if ($LASTEXITCODE -ne 0) { throw 'Schema export failed' }
# Full public archive is the independent source recovery backup, including Alembic and functions.
& "$pgBin\pg_dump.exe" --no-password --quote-all-identifiers --format=custom --schema=public --file="$backup\source-public.dump"
if ($LASTEXITCODE -ne 0) { throw 'Recovery backup failed' }
# Alembic creates the target schema. Export only app rows, in FK dependency order.
foreach ($table in $tables) {
    & "$pgBin\pg_dump.exe" --no-password --quote-all-identifiers --strict-names --data-only --no-owner --no-privileges --table="public.$table" --file="$backup\$table.sql"
    if ($LASTEXITCODE -ne 0) { throw "Data export failed: $table" }
}
$tables | Set-Content -Encoding ascii "$backup\table-order.txt"
& .\.venv\Scripts\python.exe -m scripts.database_snapshot "$backup\source-snapshot.json"
if ($LASTEXITCODE -ne 0) { throw 'Source snapshot failed' }
Get-ChildItem -LiteralPath $backup -File | Where-Object Name -ne 'checksums.csv' | Get-FileHash -Algorithm SHA256 | Export-Csv -NoTypeInformation "$backup\checksums.csv"
```

Review source-schema.sql for unexpected public objects. App tables use UUID IDs;
no application serial sequences need reseeding in the current schema. Inventory this
again if the schema changes. The archive includes `alembic_version`; **do not restore it
alongside Alembic-created tables**. Do not export Supabase/platform schemas or local roles.

## 5. Create schema, import rows, establish privileges

Use a **fresh dedicated target** with no existing CreditIQ tables. Disable Data API first.
Switch native `PG*` variables to the target direct/session operator connection, including
`PGSSLMODE=verify-full`, `PGSSLROOTCERT=<CA-path>` and a protected target password file.
Set `CREDITIQ_DB_HOSTING=supabase` and privately supply the target
`CREDITIQ_MIGRATION_DATABASE_URL` independently of these native tool variables.

```powershell
& .\.venv\Scripts\python.exe -m alembic upgrade head
if ($LASTEXITCODE -ne 0) { throw 'Alembic deployment failed' }
& .\.venv\Scripts\python.exe -m alembic current
if ($LASTEXITCODE -ne 0) { throw 'Revision verification failed' }
```

Expect `20261003_0003`. Check all 28 destination application tables are empty before import;
the application must not be running against the target. Do not TRUNCATE a populated target.
For a failed rehearsal use another fresh project/database or an explicitly reviewed cleanup.

Import the per-table files in one transaction and dependency order. Run from the backup
directory so the include paths resolve. The two circular application FKs are already
`DEFERRABLE INITIALLY DEFERRED`; other FKs are satisfied by table order. Immutable UPDATE/
DELETE triggers stay enabled; the dump only inserts rows. No superuser trigger disabling.

```powershell
$tables = Get-Content -LiteralPath "$backup\table-order.txt"
# This inventory must match the 28 names generated from the checked-out repository.
if ($tables.Count -ne 28 -or ($tables | Where-Object { $_ -notmatch '^[a-z_]+$' })) { throw 'Invalid inventory' }
$importLines = @('SET CONSTRAINTS ALL DEFERRED;')
$importLines += @($tables | ForEach-Object { '\i ' + $_ + '.sql' })
$importLines | Set-Content -Encoding ascii "$backup\import-data.sql"
Push-Location -LiteralPath $backup
try {
    & "$pgBin\psql.exe" --no-password -X --set=ON_ERROR_STOP=1 --single-transaction --file=import-data.sql
    if ($LASTEXITCODE -ne 0) { throw 'Data import failed; transaction rolled back' }
} finally { Pop-Location }
```

Do not apply source-schema.sql over the migrated schema. It is for audit/recovery review.
Do not use `--clean`, `--disable-triggers`, `session_replication_role`, or ignore SQL errors.
Cross-major compatibility failures require review and another complete rehearsal, not
an in-place partial retry. The preferred path deliberately uses Alembic for the schema.

Apply runtime grants using `psql --set=runtime_role=<restricted-role-name>` as the
operator. Scope grants to the **28 inventoried tables**; never grant all tables in a
shared public schema. For each table execute the following psql template with
`--set=table_name=<one-inventoried-name> --set=ON_ERROR_STOP=1`:

```sql
REVOKE ALL ON TABLE public.:"table_name" FROM PUBLIC, anon, authenticated, service_role;
GRANT SELECT, INSERT ON TABLE public.:"table_name" TO :"runtime_role";
```

Then apply the same mutable-table grants as the existing local runtime role:

```sql
GRANT USAGE ON SCHEMA public TO :"runtime_role";
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
REVOKE ALL ON TABLE public.alembic_version FROM PUBLIC, anon, authenticated, service_role;
REVOKE ALL ON TABLE public.alembic_version FROM :"runtime_role";
GRANT UPDATE, DELETE ON TABLE public.users, public.user_profiles, public.auth_sessions,
 public.loan_applications, public.data_consents, public.model_deployments,
 public.scoring_jobs, public.explanations, public.reports, public.outbox_events TO :"runtime_role";
REVOKE EXECUTE ON FUNCTION public.creditiq_reject_mutation(),
 public.creditiq_protect_explanation(), public.creditiq_touch_updated_at()
 FROM PUBLIC, anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.creditiq_reject_mutation(),
 public.creditiq_protect_explanation(), public.creditiq_touch_updated_at() TO :"runtime_role";
```

Verify the runtime role is not owner, superuser, a platform role or a member of an
elevated role; has no effective DDL/schema-CREATE privilege; and cannot modify immutable
records. Explicitly review default privileges for the actual migration owner before
future migrations; Supabase defaults may regrant Data API roles access to new objects.
This is an operator grant change, not a new schema migration or auth redesign.

## 6. Verification and deployment checklist

- [ ] Source backup is readable, encrypted/protected, checksummed and test-restored.
- [ ] Exact target version, IPv4/IPv6 route, TLS certificate and pool limits verified.
- [ ] Data API disabled; restricted runtime grants applied and inspected.
- [ ] Alembic head is `20261003_0003`; 28 application tables exist, plus version table.
- [ ] Source remains write-frozen. Generate target snapshot using target operator URL:
      `python -m scripts.database_snapshot <private-target-snapshot.json>`.
- [ ] Compare `revision` and every `tables` entry against source-snapshot.json. Counts
      **and SHA256 row-content digests must match**, covering users, sessions, predictions
      and all immutable records. Do not compare `server_version` for equality across
      versions; record it separately. A cross-version serialization mismatch requires
      row-level operator investigation, never treating matching counts alone as success.
- [ ] Compare source and target schema-only dumps for table definitions, indexes,
      FK/check constraints, three functions, triggers and policies. Ignore only reviewed
      owner/ACL/provider-object/version differences. All constraints validated.
- [ ] Verify active runtime connections negotiate SSL (operator checks `pg_stat_ssl`).
- [ ] With writes still stopped, update **only** backend DB environment values and restart
      workers. Confirm readiness with the restricted role and connection pool behavior.
- [ ] On a rehearsal target, verify register/login, access JWT, refresh rotation, logout,
      CSRF rejection, ownership, read-only admin access, old application/results/history,
      Installment Intelligence and planner. Check both frontend desktop/mobile.
- [ ] Run all API tests against the existing isolated **local test database**. Existing
      tests truncate data; never redirect them to the populated Supabase project.
- [ ] Run browser smoke flows on disposable rehearsal data. Do not run fixture-creating
      tests against real customer records.
- [ ] Refresh optimizer statistics with `ANALYZE` on the 28 imported tables as operator.
- [ ] After verification, resume traffic on exactly one database. Observe login errors,
      refresh failures, connection saturation, timeouts and existing prediction behavior.
- [ ] Retain source cluster, backup and previous private configuration through rollback window.

Example snapshot comparison (private paths only; no customer rows are printed):

```powershell
$source = Get-Content -Raw '<private-source-snapshot.json>' | ConvertFrom-Json
$target = Get-Content -Raw '<private-target-snapshot.json>' | ConvertFrom-Json
if ($source.revision -ne $target.revision -or
    (ConvertTo-Json -InputObject $source.tables -Depth 10 -Compress) -ne
    (ConvertTo-Json -InputObject $target.tables -Depth 10 -Compress)) {
    throw 'Migration verification mismatch: do not cut over'
}
```

## 7. Rollback

Before target writes are accepted: stop backend workers, restore the previous private
local DB configuration, restart and verify local readiness/auth; then resume local writes.
Keep the original JWT secret. Do not delete the target or source backup during investigation.

After target writes are accepted: **do not simply switch back**. Freeze all writes, snapshot
both databases and reconcile target-only accounts, sessions, applications and results.
Rehearse a reverse transfer/restore into a fresh local database, verify digests and constraints,
then cut over once. An old local snapshot would lose new records and could revive revoked
sessions. Refresh-token rotation makes simultaneous writing to both databases unsafe.
Define acceptable downtime and recovery objectives before cutover; no zero-downtime claim.

## 8. Completion boundary

This change prepared configuration, export/import instructions and verification tooling.
The active ignored `.env` now targets the supplied Supabase Session Pooler. DNS, TCP and
TLS 1.3 hostname verification succeeded, but SQLAlchemy authentication has not been tested
because the previously configured password must first be rotated and updated locally.
No remote schema inspection, Alembic migration or data transfer has occurred. Local source
rows remain authoritative. See `../Validation/SUPABASE_VALIDATION_REPORT.md` for evidence and next steps.
