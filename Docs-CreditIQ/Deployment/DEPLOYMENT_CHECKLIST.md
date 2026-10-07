> Latest code hardening and provider templates: see DEPLOYMENT_READINESS_AUDIT.md and deploy/README.md. External deployment/restore/alert gates remain open.

# CreditIQ deployment checklist

Updated 2026-10-07. Portfolio deployment only: `mode=RESEARCH_ONLY`, `release_ready=false`.

## Before deployment

- [x] Create a restricted Supabase runtime role with the existing schema's needed DML
  permissions only. No superuser, CREATE DATABASE, CREATE ROLE, BYPASSRLS, schema creation,
  migration ownership or blanket permissions. Preserve immutable-table protections.
  Completed as creditiq_runtime; see ../Validation/RUNTIME_DATABASE_ROLE_REPORT.md.
  Do not change users/authentication architecture or provision Supabase Auth.
- [x] Deny anon/authenticated/service_role database access to application data; RLS and grants verified.
- [ ] Finish Dashboard exposed-schema and keyed HTTP verification; see ../Validation/RLS_AUDIT_REPORT.md.
- [ ] Store runtime password and a fresh random JWT signing secret in the hosting secret
  manager. Remove secrets from build contexts, logs and source archives. Keep dumps private.
  The tracked example password was removed; any credential ever copied from it is disclosed.
- [ ] Set every required database field explicitly. Use Session Pooler and verify-full
  with an available provider CA file. Budget workers Ã— (pool_size + max_overflow) below
  the project connection limit, allowing operator and other services' headroom.
- [ ] Set APP_ENV=production, COOKIE_SECURE=true and exact HTTPS AUTH_ORIGINS. The API rejects
  HTTP in staging/production; configure trusted proxy scheme forwarding correctly.
- [ ] Set API_ORIGIN before frontend build. Serve frontend and its `/api` proxy on one HTTPS
  origin. Configure runtime port/bind address according to the hosting platform.
- [ ] Keep the pinned model, metadata, feature contracts and research reports available
  at their expected paths. Include required runtime libraries; no training on startup.
- [ ] Use a separate one-shot operator job for Alembic with MIGRATION_DATABASE_URL on a
  direct endpoint or the verified session endpoint. Never transaction pooling for DDL.
  Check revision 20261003_0003 and schema drift; do not rerun data import or stamp blindly.
- [ ] Configure NTP/time synchronization on the API host; JWT expiry still uses host time.
- [ ] Run dependency/security scans in the final deployment image and verify backup/PITR
  coverage, restore procedure and external network access restrictions.

## Startup and operations

- [ ] Run Uvicorn with reload disabled, bounded worker count, exact trusted proxy IPs, and
  `--no-access-log` (or a sanitized proxy logger that omits query strings and credentials).
  Do not expose the raw HTTP backend to the internet; use HTTPS termination.
- [ ] Confirm `database_startup_connected hosting=supabase` appears. Startup SELECT 1
  must succeed; database/model startup errors abort serving rather than continuing.
- [ ] Probe `/health/live` for process status and `/health/ready` for a real SELECT 1.
  Versioned aliases remain supported. Route checks through the trusted HTTPS proxy.
- [ ] Verify login, refresh, logout, owned application creation/result/history, read-only
  admin pages, planner and installment UI against deployed HTTPS with a designated account.
- [ ] Verify HttpOnly/Secure/__Host-/SameSite cookies, CSRF rejection, unauthorized origins,
  revoked sessions, owner isolation and non-admin rejection.
- [ ] Test startup without DB fields, database loss after startup, pool exhaustion and
  deployment rollback. Monitor readiness failure and sanitized database error counts.
- [ ] Keep local PostgreSQL stopped for the deployed smoke. It is only needed by isolated
  destructive integration tests, not by the deployed application.

## Rollback

Keep the previous app image and database backup. Roll back the image first; this pass
adds no table-shape changes. Security grants and RLS policies were applied separately;
preserve them during image rollback. Never silently fall back to operator credentials. Do not restore old local rows over a live Supabase database.
If database restore is needed, pause writers, back up the target, and follow the existing
migration rollback plan with explicit operator credentials. Preserve JWT signing key
and cookie origin during a routine image rollback to avoid unnecessary session resets.

Connection choices follow the [Supabase connection guide](https://supabase.com/docs/guides/database/connecting-to-postgres).
Hostname/certificate verification follows [PostgreSQL SSL documentation](https://www.postgresql.org/docs/current/libpq-ssl.html).
