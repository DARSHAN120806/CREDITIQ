> Latest code hardening and provider templates: see DEPLOYMENT_READINESS_AUDIT.md and deploy/README.md. External deployment/restore/alert gates remain open.

> Runtime role follow-up completed: active creditiq_runtime, restricted grants and RLS,
> 42 live Supabase smoke checks, 154 distinct backend tests passing across suite/rerun.
> See ../Validation/RUNTIME_DATABASE_ROLE_REPORT.md. Other deployment blockers below still apply.

# Production readiness hardening report

Date: 2026-10-07. **production_ready = false**.
`mode=RESEARCH_ONLY`, `release_ready=false` remain enforced. This is a portfolio-app
infrastructure review, not approval for real lending decisions.

## Actual deployment blockers

1. **Data API end-to-end verification pending:** the RLS follow-up applied ENABLE/FORCE
   RLS and revoked public schema/table/column/function access from anon, authenticated,
   and service_role. All 29 tables (28 application + Alembic) deny real role-switched
   SELECT attempts; row fingerprints match. Dashboard exposed-schema configuration
   and keyed HTTP validation remain unverified. See `../Validation/RLS_AUDIT_REPORT.md`.
2. **Runtime privilege blocker resolved:** active configuration now uses creditiq_runtime,
   with no administrative flags/memberships/ownership. Only 19 tables receive SELECT/INSERT,
   with column UPDATE on three tables and backend-only RLS policies. Forbidden SQL and
   real Supabase workflow checks passed. See `../Validation/RUNTIME_DATABASE_ROLE_REPORT.md`.
3. **HTTPS deployment environment not configured:** the current environment is development,
   Secure cookies are false, and origins include HTTP. This remains appropriate for local
   development but cannot pass production validation. Configure the deployment secrets,
   HTTPS origin, same-origin Next proxy, trusted proxy IPs, and Secure cookies, then run
   a smoke test through the actual deployed HTTPS origin.
4. **Final image security/operations verification pending:** backend dependency advisories,
   exposed services, restore coverage, network restrictions, proxy/header logging and
   connection budgets still need verification in the selected deployment environment.

## Issues, fixes and validation

| ID / severity | Risk | Fix applied or required | Validation result |
|---|---|---|---|
| C1 Critical | Direct Supabase role access can bypass app auth and expose user/auth data | Follow-up enforced RLS and revoked schema/table/column/function access for all three API roles | Database controls PASS; keyed HTTP and Dashboard exposure check pending. See ../Validation/RLS_AUDIT_REPORT.md |
| C2 Critical | Broad runtime role can change roles/databases and bypass RLS | Production config rejects postgres runtime users; startup checks actual PostgreSQL role flags | Resolved in runtime-role follow-up: restricted account active; staging role gate and real workflow checks pass |
| C3 Critical | A tracked environment example contained a password literal | Replaced with placeholder; private .env, backups and dumps confirmed ignored | Working template sanitized; Git history is not scrubbed, and any historically reused credential requires rotation |
| H1 High | Missing configuration silently connected to localhost | Removed host/port/database/user/password defaults; explicit configuration validation rejects missing fields and placeholders | Each missing-field test passes; local hosting forbidden in staging/production |
| H2 High | Startup could claim success while DB was unavailable | Startup SELECT 1 and fail-closed sanitized failure; engine disposed on failure | Live Supabase logged database_startup_connected; failure injection passed |
| H3 High | HTTP transport/non-Secure cookies could expose sessions | Existing HTTPS-origin/Secure-cookie checks retained; deployment middleware rejects HTTP and adds HSTS | Unit HTTPS/CORS/HSTS checks passed; deployed HTTPS smoke pending |
| H4 High | Old transitive PostCSS has reported file-disclosure/XSS advisories | Override Next's PostCSS to 8.5.28, preserve Next 15.5.27; update lockfile | Final production npm audit: 0 vulnerabilities; rebuild/browser validation recorded below |
| H5 High | Unhandled error tracebacks may expose SQL, passwords or tokens in Uvicorn logs | Boundary catches unexpected request failures; logs event/type only, generic response; SQLAlchemy parameters hidden | Secret-bearing injected failures return 500 without secret logs; transaction rollback assertions retained |
| M1 Medium | Liveness falsely used as database readiness | Add /health/live and /health/ready plus preserved versioned aliases; readiness runs SELECT 1 and uses no-store | Supabase both 200; injected outage produces readiness 503 while liveness stays 200 |
| M2 Medium | Pool exhaustion and long DB/lock waits; pooler ignored startup timeout options | Configurable waits, recycling/pre-ping; apply SET LOCAL timeouts on each transaction instead of driver startup options | Real Supabase SHOW returned statement_timeout=15s and lock_timeout=5s; load testing pending |
| M3 Medium | Automatic retries could duplicate transactional writes | No automatic write retries; startup fails once, orchestrator controls restart | Existing idempotency and rollback backend tests pass |
| M4 Medium | Operator credentials/transaction pooler used for DDL | Separate explicit operator migration URL; reject local Supabase targets and shared transaction-pooler port | URL validation/offline migration tests pass; no migrations run, revision unchanged |
| M5 Medium | Frontend build could silently proxy to localhost | Production build/start requires explicit API_ORIGIN, rejects credential-bearing/invalid origins | Missing-origin production check and configured build validated; set deployed HTTPS API target |
| M6 Medium | Dark-theme CSS restores desktop columns on mobile, making forms/charts unusable | Restore single-column shell after dark-theme overrides | Browser mobile overflow checks rerun below |
| M7 Medium | Host time skew affects JWT expiry and rate-limit windows | Existing persisted revocation clock fix retained; require synchronized deployment host clocks | Revocation regression passed; deploy NTP verification pending |
| L1 Low | Light-theme browser assertions were stale | Update amber background and disclaimer color expectations for current dark theme | Updated visual assertions pass |
| L2 Low | TestClient deprecation and Windows test-cache permission warnings | Recorded existing Starlette/httpx warning and final pytest cache write warning; no unrelated runtime dependency change | Backend suite passes; cache warning does not affect assertions |

## Authentication, sessions and secrets audit

Argon2id password hashing, opaque hashed refresh tokens, rotation, replay/family revocation,
logout, server-side session checks, role/ownership checks and CSRF remain implemented.
JWT decode pins HS256 and requires issuer/audience/time/identity/purpose claims. Production
requires a signing secret of at least 32 bytes. Auth cookies are HttpOnly (except CSRF),
host-only, Path=/, SameSite=Strict and Secure with __Host- names. Cross-site API/frontend
deployment is not supported by these Strict-cookie semantics; retain the Next same-origin
proxy. CORS uses exact origins and credential-aware responses; staging/production rejects
non-HTTPS origins. Admin API routes remain read-only.

Never enable SQL echo or request-body logging. Use Uvicorn --no-access-log or a redacting
proxy logger; avoid logging query strings, cookies, Authorization headers or URLs with
credentials. Only safe error class names and static event codes are logged by added
application handlers. Test credentials are public fixtures for the disposable database,
not deployment accounts. No Supabase Auth, anon key or service-role key is needed by this
backend.

## Supabase, migrations and preservation

Active development runtime still uses the verified Supabase Session Pooler with TLS
verify-full, pool size 5 and max overflow 0. Startup and readiness checks use the real
runtime connection. Direct `.supabase.co` and pooler `.supabase.com` endpoints are accepted;
local endpoints are not accepted for Supabase hosting. Explicit local configuration remains
available only for development/test; there is no implicit local database fallback.

Supabase revision remains **20261003_0003**. The original hardening pass contained no remote grant changes; the subsequent RLS
follow-up applied security DDL without changing revision. Both passes made no retraining, no model/contract edits, and no prediction/formula
changes. Destructive tests run only against the isolated `creditiq_migration_test` database.
Live Supabase hardening checks are SELECT-only and do not create auth-rate events.

## Validation results

- Final full backend suite after the transaction-timeout fix: **153 passed** in 222.35s;
  2 warnings (Starlette/httpx deprecation, Windows pytest-cache permission warning).
- Real Supabase startup SELECT 1: **passed**, successful startup event captured.
- Real Supabase `/health/live` and `/health/ready`: **200**, expected JSON responses.
- Supabase startup/readiness with local PostgreSQL stopped: **passed**; revision unchanged.
- Shared and dedicated transaction-pooler migration URLs: rejected in regression checks.
- Frontend TypeScript check: **passed**.
- Production frontend build: **passed**, including TypeScript checks and page generation.
- Full browser rerun on the final patched build: **38 passed** in 1.4 minutes.
- Production frontend build without API_ORIGIN: **rejected as expected before compilation**.
- Final production npm advisory audit: **0 vulnerabilities** after the PostCSS override.
- Initial browser rerun: **36 passed, 2 failed**; both failures were real mobile overflow
  caused by the dark-theme breakpoint override, subsequently corrected.

See DEPLOYMENT_CHECKLIST.md and ENVIRONMENT_VARIABLES_REFERENCE.md for the exact operator
checks and supported configuration. Completing code hardening does not remove the remote
role/grant and deployed HTTPS verification blockers above.
