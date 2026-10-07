# Environment variables reference

Updated 2026-10-07. API settings use the `CREDITIQ_` prefix. Deployment environment
variables override `services/api/.env`; that private file is for development only.
Never bundle it, `.postgres`, database dumps, credentials, or public browser-test passwords.
There is no API `DATABASE_URL` consumer: the runtime URL is built from the fields below.

## Database runtime

| Variable | Required/default | Purpose |
|---|---|---|
| CREDITIQ_PG_HOST | Required | Supabase endpoint copied from Connect panel; no localhost default |
| CREDITIQ_PG_PORT | Required | Session/direct 5432 or explicit transaction port |
| CREDITIQ_PG_DATABASE | Required | Target database |
| CREDITIQ_PG_USER | Required | Restricted runtime role; pooled username includes project suffix |
| CREDITIQ_PG_PASSWORD | Required, secret | Runtime role password; missing/placeholder values rejected |
| CREDITIQ_DB_HOSTING | supabase | `local` is an explicit development/test option; forbidden in staging/production |
| CREDITIQ_PG_CONNECTION_MODE | direct | Set explicitly to `session` for the current pooler; transaction mode disables prepared statements |
| CREDITIQ_PG_SSLMODE | prefer | Set `verify-full`; mandatory in staging/production |
| CREDITIQ_PG_SSLROOTCERT | Optional | Mounted CA certificate file; an explicitly configured missing file is rejected |
| CREDITIQ_DB_POOL_SIZE | 5 | Per-worker steady connection budget |
| CREDITIQ_DB_MAX_OVERFLOW | 5 | Extra per-worker connections; recommend 0 initially |
| CREDITIQ_DB_CONNECT_TIMEOUT | 5 seconds | Initial network/auth connection bound, maximum 30 |
| CREDITIQ_DB_POOL_TIMEOUT | 30 seconds | Wait for available pool slot, maximum 60 |
| CREDITIQ_DB_POOL_RECYCLE | 300 seconds | Reconnect aged pooled connections when next checked out |
| CREDITIQ_DB_STATEMENT_TIMEOUT_MS | 15000 | PostgreSQL statement execution timeout |
| CREDITIQ_DB_LOCK_TIMEOUT_MS | 5000 | PostgreSQL lock acquisition timeout |
| CREDITIQ_MIGRATION_DATABASE_URL | Operator only, secret | Explicit postgresql+psycopg direct/session operator URL with TLS; never add to API service |

Runtime validates the required fields before serving, performs SELECT 1 during startup,
and rejects privileged roles in staging/production. No automatic migrations or write
retries occur. Database disconnection returns a sanitized 503. Pool pre-ping is enabled.
Statement/lock timeouts use SET LOCAL for every transaction; driver startup options alone
were ignored by the real pooler. Verified live values are 15 seconds and 5 seconds.
The migration operator URL never silently inherits the Supabase runtime URL.

## Application and authentication

| Variable | Default / deployment requirement |
|---|---|
| CREDITIQ_APP_ENV | development; **set production explicitly** for deployment |
| CREDITIQ_MODE | RESEARCH_ONLY; cannot enable lending mode |
| CREDITIQ_RELEASE_READY | false; cannot enable model release approval |
| CREDITIQ_LITE_ENABLED | true; preserve this for application scoring |
| CREDITIQ_JWT_SECRET | Required secret, minimum 32 bytes; generate cryptographically, share across workers |
| CREDITIQ_JWT_ISSUER | creditiq-api |
| CREDITIQ_JWT_AUDIENCE | creditiq-web |
| CREDITIQ_ACCESS_TOKEN_MINUTES | 15; bounded 1â€“30 |
| CREDITIQ_REFRESH_TOKEN_DAYS | 30; bounded 1â€“30 |
| CREDITIQ_COOKIE_SECURE | true; mandatory for staging/production |
| CREDITIQ_AUTH_ORIGINS | Development loopback defaults; replace with exact HTTPS origins as JSON array |
| CREDITIQ_AUTH_IP_LIMIT | 120 per rolling window |
| CREDITIQ_AUTH_ACCOUNT_LIMIT | 10 per rolling window |
| CREDITIQ_AUTH_WINDOW_SECONDS | 900 |

Access/refresh cookies are HttpOnly, host-only, Secure in deployment, SameSite=Strict,
and Path=/; Secure mode uses the __Host- prefix. CSRF cookie is intentionally readable
by JavaScript. CSRF tokens bind to the refresh token and exact allowed origin. JWTs use
HS256 with algorithm, issuer, audience, time and purpose checks; role/session state is
checked in PostgreSQL on authenticated requests. Refresh rotation, replay revocation and
logout remain unchanged. Rotate JWT keys only with a session/sign-in transition plan.

## Frontend, server and test operators

| Variable | Purpose |
|---|---|
| API_ORIGIN | Next server-side API rewrite target; explicitly configure deployed backend URL before build |
| CREDITIQ_WEB_DIST_DIR | Optional isolated Next build folder; default .next |
| PORT | Next production listening port, supplied by host or CLI |
| FORWARDED_ALLOW_IPS | Uvicorn trusted proxy IPs; configure exact proxy addresses, not arbitrary internet clients |
| CREDITIQ_TEST_POSTGRES | Opt-in destructive tests on creditiq_migration_test only; never enable in deployment |
| CREDITIQ_PG_BIN | Local test/operator PostgreSQL binary path only |
| PLAYWRIGHT_BASE_URL | Browser-test frontend origin only |

The frontend's development API_ORIGIN default is loopback HTTP; production build/start
rejects missing API_ORIGIN and credential-bearing/non-origin URLs. Configure it at build
and runtime. No database credential is NEXT_PUBLIC or sent to the browser. Preserve
the same-origin `/api` proxy so Strict cookies and CSRF work; arbitrary cross-site frontend
and API deployment is not supported by the current cookie design.

## Restricted runtime cutover (2026-10-07)

Active PG_USER is creditiq_runtime.pzknfundavkxzxtrikbq, with its own generated password.
The Session Pooler and TLS settings are unchanged. The role's 20-connection limit is a
shared upper bound; budget all API workers below it. It has 19-table read/insert access
and four update columns across three tables; see ../Validation/RUNTIME_DATABASE_ROLE_REPORT.md.

The operator URL is retained only in ignored services/api/.postgres/supabase-operator.env.
Load it explicitly into a separate operator command environment for Alembic or security
scripts, then remove it from that environment. Do not deploy .postgres or use its private
backup/candidate files as frontend assets or build inputs. API settings do not load them.
Restart existing API processes after changing .env; changing a file does not replace
already-open operator database connections.

## Deployment-only settings added

CREDITIQ_API_ORIGIN and CREDITIQ_FRONTEND_ORIGIN: required HTTPS origins in staging/production.
CREDITIQ_AUTH_ORIGINS must equal the one-element frontend-origin list for the same-origin proxy.
CREDITIQ_TRUSTED_PROXY_IPS: explicit comma-separated IPs/CIDRs, never wildcard or /0.
CREDITIQ_DEPLOYMENT=true: frontend image/build flag requiring a public HTTPS API_ORIGIN.
PORT: provider listening port; start_server.py defaults to 8000. BIND_HOST defaults to 0.0.0.0;
VPS systemd binds loopback. Deployment runner uses one worker and disables access logs/reload.
Production/staging env templates and provider runbook: root env examples and deploy/README.md.
No production origin, proxy address or provider secret is inferred from developer settings.
