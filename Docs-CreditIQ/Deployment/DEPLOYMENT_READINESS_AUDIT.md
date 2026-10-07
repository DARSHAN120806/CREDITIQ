# CreditIQ deployment readiness audit

Date: 2026-10-07. **PRODUCTION_READY = false.**

Code hardening and deployment preparation were applied, not merely proposed. No provider
deployment, database migration, model retraining, or customer-data change was performed.
The active developer .env remains usable; it was not changed to invented production domains.
Supabase and creditiq_runtime remain active. Local PostgreSQL was used only for disposable
regression tests and stopped afterwards. mode=RESEARCH_ONLY; release_ready=false.

## Requirement-by-requirement result

PASS means supported by executed checks or inspected configuration. FAIL includes missing
external evidence: it does not necessarily mean an exploitable defect was demonstrated.

| Requirement | Result | Exact fix / evidence / file reference |
|---|---|---|
| Supabase primary database; no silent local fallback | PASS | Existing fail-closed database checks retained, services/api/app/core/config.py:69; live restricted-role workflow validation passed |
| Restricted runtime account | PASS | creditiq_runtime; startup now rejects REPLICATION as well as superuser/CREATEDB/CREATEROLE/BYPASSRLS, services/api/app/main.py:41 |
| RLS and API-role grants | PASS | Prior verified security configuration preserved; no new grants/policies in this task; ../Validation/RLS_AUDIT_REPORT.md and ../Validation/RUNTIME_DATABASE_ROLE_REPORT.md |
| Production environment actually selected | FAIL | Active developer environment is development. production.env.example and staging.env.example supplied. scripts/start_server.py refuses development/test deployments |
| Production cookie configuration actually deployed | FAIL | Developer COOKIE_SECURE=false retained. Templates require true; config.py and startup_environment_validator.py reject insecure staging/production settings |
| Explicit HTTPS API/frontend/auth origins | FAIL | Guards and templates implemented; real provider domains have not been supplied or verified. app/core/startup_environment_validator.py:6 |
| Trusted reverse proxy configured | FAIL | Explicit IP/CIDR allowlist now required; wildcard and /0 rejected. scripts/start_server.py passes the validated list to Uvicorn. Actual provider ingress/firewall/header rewriting unverified |
| Required environment settings and TLS fail closed | PASS | Missing DB settings, local hosting, postgres runtime, insecure TLS and missing deployment origins/proxy settings reject startup; deployment unit tests passed |
| Strong JWT configuration checks | PASS | Existing minimum length plus placeholder, low-diversity and repeated-pattern rejection. startup_environment_validator.py. This is not an entropy proof: generate secrets cryptographically |
| No operator secret in deployed API config | PASS | Validator rejects migration_database_url in staging/production; runtime .env has none; operator remains in private ignored files |
| Safe startup diagnostics | PASS | main.py:49 logs environment, host/port/database, role, SSL mode, cookie security, API/frontend origins from an allowlist; password/JWT excluded; tests verify redaction |
| Real database health/readiness | PASS | Existing SELECT 1 readiness and startup preserved. Health-only GET routes may use plain HTTP for orchestrators; all business/auth routes remain HTTPS-only in staging/production. auth/middleware.py:17 |
| CreditIQ publishable-key and Data API dependency audit | PASS | No SDK/key/REST/Auth/Storage integration in source, manifests, templates, or active env names. Direct PostgreSQL only; see ../Validation/SUPABASE_PUBLISHABLE_KEY_AUDIT.md |
| Supabase Dashboard exposed-schema setting | FAIL / external | Project-level control-plane toggle was not inspected. DB ACL/RLS denies anon/authenticated/service_role on the 29 public tables; CreditIQ needs no publishable key |
| Build-context secret exclusion | PASS | .dockerignore defaults to deny; deploy/package_artifacts.py allowlists artifacts; deploy/deploy.py prepares a clean Railway context. 131 staged files scanned: no env files, dumps, active/runtime/operator password or JWT values |
| Provider secret store and historical rotation verification | FAIL | Templates contain placeholders only; provider secret store not configured/audited. Developer backups/operator files must never be deployed. Historical secret reuse/rotation must be confirmed |
| Model/dashboard artifact packaging | PASS | 30-file private bundle; hashes match; bundled Lite model and both research dashboards load. Original artifacts unchanged |
| Backend dependencies | PASS | pip-audit scanned all 62 pinned dependencies, none skipped, zero known advisories; pip check passed. Actual Linux image/OS scan still required |
| Frontend dependencies/build | PASS | npm production audit: zero vulnerabilities; TypeScript and production build passed. Deployed HTTP/localhost API_ORIGIN rejected by next.config.ts:8 |
| Linux container build and provider manifests executed | FAIL | Docker unavailable on this host. Dockerfiles, Compose/Render YAML and Railway JSON supplied; YAML/JSON parsed, but no image build, provider deploy or systemd execution claimed |
| Regression tests | PASS | 172 full backend tests passed; 2 additional deployment-tool tests passed separately. 42 live rollback-only Supabase workflow checks passed; no data changed |
| Hosted browser/auth/session validation | FAIL | No HTTPS staging deployment exists. Local frontend build passed; prior 38 browser tests remain historical evidence, not a new hosted test run |
| Backup/PITR availability and restore proof | FAIL | Provider plan/retention not verified; isolated restore drill not performed. deploy/README.md documents private operator backup and isolated verification procedure |
| Monitoring implementation | PASS | deploy/monitor.py, creditiq-monitor.service and .timer added; healthy/failure/alert path tests pass without sending messages |
| Monitoring and alert delivery operational | FAIL | No independent monitor host or alert receiver configured/tested. Provider deduplication/escalation and actual failure delivery required |
| Production load, pool/memory and outage testing | FAIL | One worker and 5+0 application pool retained; runtime role limit 20; container initial memory limit 2 GiB. Hosted resource adequacy remains unmeasured |
| Release and rollback procedure | PASS | deploy/README.md: compatible immutable image rollback, preserve Supabase/RLS/runtime role; no automatic migration or local fallback |
| Staging promotion / deployment checklist complete | FAIL | Provider/domains/account access pending; checklist updated, not marked complete without evidence |

## Implementation inventory

### Backend

- `services/api/app/core/startup_environment_validator.py`: shared deployment guard and safe summary.
- `services/api/app/core/config.py`: API/frontend origin and trusted-proxy fields.
- `services/api/app/main.py`: invokes validator, logs safe summary, checks replication privilege.
- `services/api/app/auth/middleware.py`: precise GET-only health probe exception for private HTTP orchestration; no auth/business HTTP exception.
- `services/api/scripts/start_server.py`: common production/staging Uvicorn entrypoint, explicit proxy trust, one worker, no access log or reload.
- `services/api/scripts/deployment_validation.py`: nonzero failure on invalid deployment config; optional real DB/artifact/HTTPS checks; no migrations or writes. Generic error classes avoid leaking secret URLs.
- `services/api/scripts/validate_runtime_role.py`: staging smoke configuration now supplies required origins/proxy settings.

### Templates, deployment and packaging

- Root `production.env.example`, `staging.env.example`: secure defaults and explicit placeholders.
- `.dockerignore`, `.gitignore`: narrow container context and private generated assets/context ignored by Git.
- `deploy/api.Dockerfile`, `deploy/web.Dockerfile`: locked dependencies, non-root runtime; frontend listens on platform port and requires deployed HTTPS origin.
- `deploy/compose.yaml`: private immutable image references, loopback ports, isolated backend secrets, CA mount, restricted API container.
- `deploy/railway-api.json`, `deploy/railway-web.json`, `deploy/render.yaml`: provider configurations.
- `deploy/deploy.py`: explicit Railway, Render, Coolify, Compose and systemd adapters; no speculative account creation or automatic migrations. Provider setup is documented in `deploy/README.md`.
- `deploy/creditiq-api.service`, `deploy/creditiq-web.service`, `deploy/Caddyfile`: VPS service/TLS templates.
- `deploy/package_artifacts.py`: checksum-checked allowlist bundle. Lite's existing checksum contract requires saved research parquet partitions; these are included privately, never served as frontend assets. Raw CSVs and database backups are excluded.
- `deploy/monitor.py`, `deploy/creditiq-monitor.service`, `deploy/creditiq-monitor.timer`: independent-host polling and generic JSON alert delivery. Minimal implementation sends one alert per failed run; provider must handle deduplication/escalation.
- `apps/web/next.config.ts`: deployment-marked builds refuse insecure/loopback API origins; local development/test builds remain supported.

### Tests

- `services/api/tests/test_deployment.py`: startup guard matrix and secret-free summary.
- `services/api/tests/test_deployment_tools.py`: monitor healthy/failure paths and provider missing-config refusal.
- `services/api/tests/test_hardening.py`: explicit valid deployment settings and health-only HTTP exception assertions.

## Executed validation

1. Full isolated backend suite: **172 passed**, one existing Starlette/httpx deprecation warning, 215.47 seconds.
2. Additional tool tests added afterwards: **2 passed**. Total **174 distinct tests passed**, not a claim of one 174-test invocation.
3. Real Supabase staging-mode workflow smoke: **42 checks passed**, enclosing transaction rolled back; fingerprints unchanged.
4. Frontend typecheck and production build: **passed**, using a reserved example HTTPS API domain for build validation only.
5. Negative deployment build with HTTP localhost API origin: **failed as intended** before building.
6. Active developer configuration passed to deployment_validation.py: **failed as intended**, because it is development with non-Secure cookies and no deployment origins. A deployment-only gate does not silently promote it.
7. Private artifact bundle: **30 hashes matched**; Lite and both dashboards load from the bundle.
8. Railway clean upload context: **131 files**, no environment files/dumps or actual current runtime/operator/JWT secret bytes. Context was not uploaded.
9. Railway JSON and Render/Compose YAML parsing: **passed**. Python compile checks and Git whitespace checks passed.
10. Production npm audit: **0 vulnerabilities**. Pinned backend audit: **62 dependencies, 0 skipped, 0 known vulnerabilities**. pip check: no broken requirements. Isolated audit tool installation did not modify backend dependencies.
11. Read-only deployment_validation.py database/artifact checks: **passed** against real Supabase with synthetic explicit staging HTTPS origins; no hosted HTTPS request or deployment was claimed. Local PostgreSQL was stopped.
12. Docker/systemd/provider deployment: **not run** (Docker unavailable, Windows host, no provider target configured). Browser deployment smoke, restore drill and external alert delivery: **not run**.

## Remaining manual actions and order

1. Select host and real staging API/frontend domains; provision DNS/TLS, provider secret store,
   CA certificate mount, exact ingress trust and network restrictions. Private operator credentials
   remain separate; never deploy .postgres or local env/backups.
2. Verify the Supabase Dashboard exposed-schema setting if the project must guarantee that
   `public` is not listed there; also verify actual backup/PITR entitlement,
   and an isolated restore including fingerprints and RLS/grants (security DDL is outside Alembic).
3. Build and scan the Linux images, verify pinned ML wheels/model loading, and use private
   immutable image tags. Frontend API_ORIGIN must match at build and runtime.
4. Deploy staging using one adapter. Run deployment_validation.py with --database --artifacts
   --https and run real browser login/CSRF/refresh/logout/ownership/admin/model workflows.
5. Install external monitoring, test receiver delivery and escalation, then perform basic
   load/outage/rollback checks. Document connection and memory budgets and time synchronization.
6. Promote the same tested artifacts/configuration to production and complete the checklist.

## Verdict

**PRODUCTION_READY = false â€” NO-GO for public production.**

The code-level startup and packaging controls are implemented and validated. Remaining
gates require actual infrastructure, provider settings, credentials/domains, restore and
alert evidence. No production environment, backup proof or deployment success is fabricated.
For real lending use, the unchanged research-only model restrictions are an additional block.
