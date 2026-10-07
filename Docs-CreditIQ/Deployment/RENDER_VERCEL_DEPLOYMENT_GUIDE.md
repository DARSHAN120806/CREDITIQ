# CreditIQ GitHub → Render deployment guide

Updated: 2026-10-08. This now uses Render's native Python runtime and deploys directly
from the GitHub repository. Docker is not used for this service. No provider deploy,
database write, migration, or model retraining was performed here.

CreditIQ remains `RESEARCH_ONLY`; `release_ready=false`.

## Render service settings

Create a **Web Service** connected to the GitHub repository and select the branch to
deploy. Use these exact values (also recorded in `deploy/render.yaml`):

| Setting | Value |
|---|---|
| Runtime | Python |
| Root Directory | `.` (repository root) |
| Python version | `3.12` from the root `.python-version` file |
| Build Command | `pip install -r services/api/requirements-lock.txt && python deploy/prepare_render_assets.py` |
| Start Command | `cd services/api && python -m scripts.start_server` |
| Health Check Path | `/health/ready` |
| Port | `10000` (`PORT` supplied by Render and read by the existing entrypoint) |
| Region | Singapore, near the Supabase ap-south pooler |

The existing entrypoint runs Uvicorn on `0.0.0.0:$PORT`, with one worker, no reload, and
proxy-header parsing disabled on Render web services. Render's native Web Service runtime requires
binding to `0.0.0.0` and recommends its `PORT` environment variable; its default port is
10000. Render HTTP readiness checks accept a successful 2xx/3xx response, and this
project's ready route performs `SELECT 1`. [Render web services](https://render.com/docs/web-services),
[Render health checks](https://render.com/docs/health-checks)

## Why the build copies runtime artifacts

A clean Git checkout currently lacks the model and dashboard artifacts because
`ml/real_data_output/` and `ml/research_output/` are ignored by Git. The API loads the Lite
artifact during startup and serves model research and segmentation pages from those
directories. Without runtime artifacts, a Git-only deploy would fail at startup or make
those pages unavailable.

To make this direct Git deployment work, `deploy/render-assets/` contains byte-for-byte
copies of the existing 30-file allowlisted deployment bundle (about 24 MiB) and its
SHA-256 manifest. `deploy/prepare_render_assets.py` checks every file against the
manifest, rejects unsafe paths and mismatches, and copies files to the paths already
expected by the API. It does not train, edit, or replace an existing different artifact.
The application still verifies its pinned model and source checksums at startup.

**Keep the GitHub repository private.** The bundle includes derived feature/prediction
Parquet files used by the existing research artifact contract. They must not be exposed
through a public source repository or frontend. The package is server-side runtime data;
do not copy it to `apps/web/public`.

## Required Render environment variables

Create the `creditiq-api-secrets` environment group referenced by `deploy/render.yaml`.
Set these values in Render's Environment UI, never in Git:

| Variable | Value / rule |
|---|---|
| `CREDITIQ_APP_ENV` | `production` (or `staging` for a staging service) |
| `CREDITIQ_MODE` | `RESEARCH_ONLY` |
| `CREDITIQ_RELEASE_READY` | `false` |
| `CREDITIQ_DB_HOSTING` | `supabase` |
| `CREDITIQ_PG_HOST` | Supabase Session Pooler host |
| `CREDITIQ_PG_PORT` | Session Pooler port, currently `5432` |
| `CREDITIQ_PG_DATABASE` | `postgres` |
| `CREDITIQ_PG_USER` | `creditiq_runtime.<project-ref>` pooler username |
| `CREDITIQ_PG_PASSWORD` | Rotated password for the restricted runtime role |
| `CREDITIQ_PG_CONNECTION_MODE` | `session` |
| `CREDITIQ_PG_SSLMODE` | `verify-full` |
| `CREDITIQ_PG_SSLROOTCERT` | `/etc/secrets/supabase-ca.crt` |
| `CREDITIQ_DB_POOL_SIZE` | `5` |
| `CREDITIQ_DB_MAX_OVERFLOW` | `0` |
| `CREDITIQ_COOKIE_SECURE` | `true` |
| `CREDITIQ_JWT_SECRET` | New random value from `python -c "import secrets; print(secrets.token_urlsafe(48))"`; do not rotate on each deploy |
| `CREDITIQ_API_ORIGIN` | Exact public API origin, for example `https://<service>.onrender.com` |
| `CREDITIQ_FRONTEND_ORIGIN` | Exact HTTPS Vercel production origin |
| `CREDITIQ_AUTH_ORIGINS` | JSON list containing only that exact frontend origin |
| `CREDITIQ_TRUSTED_PROXY_IPS` | Leave unset on Render web services; startup rejects a value there |
| `CREDITIQ_LITE_ENABLED` | `true` |
| `PORT` | Blueprint sets `10000`; Render also supplies this variable |

Upload the Supabase CA certificate in the Render service's **Secret Files** section as
`supabase-ca.crt`. Native Render services expose secret files at
`/etc/secrets/<filename>`. Do not add `CREDITIQ_MIGRATION_DATABASE_URL`, operator
credentials, `.env`, database dumps, or model files as Vercel variables.
[Render environment variables and secret files](https://render.com/docs/configure-environment-variables)

The active local `.env` is `development` with `COOKIE_SECURE=false`; it was intentionally
left untouched. It must not be uploaded to Render. Deployment startup rejects these
values and requires explicit HTTPS origins.

## Render HTTPS boundary

Render redirects public HTTP to HTTPS and forwards requests to the web service over HTTP.
The backend recognizes Render's documented `RENDER=true` and `RENDER_SERVICE_TYPE=web`
runtime markers, disables Uvicorn's forwarded-header parsing and leaves
`CREDITIQ_TRUSTED_PROXY_IPS` unset. HSTS, Secure cookies, and HTTPS API/frontend origin
requirements remain in place. The application cannot independently prove that an
internal HTTP request passed through Render's public TLS edge. Other services in the
same Render workspace/region may reach the web service over its private network;
restrict access to that workspace and do not treat this mode as end-to-end TLS.
Other hosts retain the explicit proxy allowlist and application HTTPS check.

## Supabase and local PostgreSQL validation

In this workspace, the configured SQLAlchemy connection used the Supabase Session Pooler,
`verify-full` TLS, and the restricted `creditiq_runtime` identity. Read-only `SELECT 1`
and the same restricted-role privilege query used by production startup succeeded. The
local PostgreSQL port `127.0.0.1:55432` was unreachable. No migration or database write
was run.

This proves the current environment can reach Supabase without local PostgreSQL; it does
not prove Render egress, its mounted CA permissions, or an actual hosted deploy. The app
startup path creates the engine, runs `SELECT 1`, checks the runtime role in deployment
mode, loads the unchanged Lite artifact, and then serves `/health/live` and
`/health/ready`. Hosted verification remains required.

## Vercel frontend compatibility

The existing frontend remains deployable separately on Vercel:

- Root Directory: `apps/web`
- Framework: Next.js
- Node.js: `22.x`
- Build: `npm run build`
- Environment variables for each required deployment target: `API_ORIGIN` set to the
  Render HTTPS origin and `CREDITIQ_DEPLOYMENT=true`

`apps/web/next.config.ts` already requires `API_ORIGIN` for production, enforces HTTPS
when deployed, and rewrites `/api/:path*` to the backend. The browser should keep calling
the same-origin Vercel `/api` path so existing host-only auth cookies and CSRF behavior
remain intact. No frontend source changes were needed. Vercel's Next.js configuration
uses the app package build script and supports a monorepo project root.
[Vercel build configuration](https://vercel.com/docs/builds/configure-a-build)

## Validation performed

- `deploy/prepare_render_assets.py` verifies the complete manifest and current artifact
  files without overwriting different files.
- Render Blueprint parsed and its runtime/root/build/start/health/port fields were
  checked.
- Render entrypoint source reads `PORT` and binds `0.0.0.0`; its local port selection was
  checked with a non-default port value.
- FastAPI lifespan smoke against Supabase loaded the Lite artifact; `/health/live` and
  `/health/ready` both returned 200.
- Read-only SQLAlchemy `SELECT 1` succeeded as `creditiq_runtime`; local PostgreSQL was
  unreachable.
- Frontend `npm run typecheck` and production `npm run build` passed with the deployed
  HTTPS guard enabled.
- Deployment-specific backend tests previously passed: 20 passed, one existing
  Starlette/httpx deprecation warning.
- No Render service deployment was performed. Render service settings, production
  secrets, domain, external login/registration, and hosted writes remain
  to be verified after provisioning.

## Deployment checklist

Before deploy:

- [ ] Keep the GitHub repository private and push the code plus `deploy/render-assets/`.
- [ ] In Render, connect the repository and apply the settings in the table above.
- [ ] Create/populate `creditiq-api-secrets`; upload the CA secret file.
- [ ] Leave `CREDITIQ_TRUSTED_PROXY_IPS` unset and confirm the service reports
  `https_enforcement=render_edge` in its sanitized startup log.
- [ ] Set final HTTPS Render/Vercel origins and fresh secrets.
- [ ] Choose a plan with enough memory for the loaded model and dependencies; Free is
  only suitable for a disposable preview because it idles/sleeps and has limited CPU/RAM.

After deploy:

- [ ] `/health/live` returns 200.
- [ ] `/health/ready` returns 200 and its database check is green.
- [ ] Logs report Supabase startup and the restricted runtime role without exposing
  secrets.
- [ ] Through Vercel, verify registration, login, CSRF, refresh, logout, and session
  revocation using a non-test account.
- [ ] Create and retrieve a prediction; verify application data in Supabase and ownership
  enforcement.
- [ ] Verify Secure/HttpOnly/SameSite host-only cookies and no token in localStorage.
- [ ] Verify model research and segmentation pages load packaged artifacts and admin stays
  read-only.

## Status

**Git-backed, no-Docker configuration is prepared. Actual Render verification is still
blocked** until the private repository is pushed and service secrets/domains are configured.
`PORT`, Supabase credentials/TLS,
and the local stopped-database path have been verified from this workspace; hosted Render
health checks cannot be claimed before a service exists.
