# CreditIQ backend â€” Milestones 1â€“3

**Research prototype update (3 October 2026):** Application/result/history APIs, pinned Lite scoring and read-only admin APIs are implemented. See ../../PROTOTYPE_VALIDATION.md for the exact contracts, files and current test evidence, and ../../apps/web/README.md for the connected Next.js UI. Existing schema/migrations/auth are reused; model loading now occurs at API startup when CREDITIQ_LITE_ENABLED=true (default). Earlier milestone-only descriptions below are historical. No training or deployment occurs.


FastAPI foundation, 24-table PostgreSQL schema and authentication/session/RBAC services. See [AUTHENTICATION.md](AUTHENTICATION.md) for endpoints, cookie/CSRF integration, security controls and operator instructions. Prediction/model loading, admin business APIs and frontend remain unimplemented. Built-in `/docs`, `/redoc` and `/openapi.json` remain available for local inspection.

## Local setup (PowerShell)

Use Python 3.12. From the repository root, the existing ML interpreter can create an independent environment without installing backend packages into the ML environment:

```powershell
.\ml\.venv\Scripts\python.exe -m venv services/api/.venv
Set-Location services/api
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
Copy-Item .env.example .env
```

Edit `.env` with your local PostgreSQL connection settings and a freshly generated JWT secret (recommend Python secrets.token_urlsafe(48)). Configure exact browser origins and cookie settings as described in AUTHENTICATION.md. **This workspace now has a configured, ignored .env; do not overwrite it.** The example contains no working credentials. The lock records the tested Python 3.12 Windows environment, including development tools; requirements.txt and requirements-dev.txt define direct dependency ranges.

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Visit `http://127.0.0.1:8000/api/v1/health/live` or `/docs`. Startup creates a lazy SQLAlchemy engine and session factory; it does not connect to PostgreSQL, create tables, run migrations or load an ML model. Liveness is not database/model readiness. Milestone 2 verified a separate local PostgreSQL 18.6 cluster on 127.0.0.1:55432, development database creditiq, restricted runtime role creditiq_app, and disposable database creditiq_migration_test. The two existing Windows PostgreSQL instances were left unchanged.

## Configuration

`app/core/config.py` reads `CREDITIQ_` environment variables and the service-local `.env`. Environment values override `.env`. Settings are typed, port/pool bounds are validated, and passwords use SecretStr. PostgreSQL uses the synchronous psycopg 3 driver. SSL defaults to `prefer` for local development; later deployment must choose its verified TLS policy explicitly. Staging/production configuration requires Secure cookies and HTTPS origins, but never enables lending production mode.

## Validation and migrations

Run from `services/api`:

```powershell
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m alembic heads
.\.venv\Scripts\python.exe -m alembic upgrade head --sql
```

The current head is **20261003_0002**. `schema.sql` is the PostgreSQL offline SQL export of both migrations, including triggers; do not apply it on top of an Alembic-managed database. No create_all fallback is provided. The frozen migration contains explicit operations and does not import live application metadata.

## Project-local PostgreSQL operator commands

Run from services/api, with the service stopped only when explicitly requested:

```powershell
# Start only if this project-local cluster is stopped (not a Windows service).
.\.venv\Scripts\python.exe -m scripts.local_db start
# Apply reviewed migrations with the isolated cluster's owner credentials.
.\.venv\Scripts\python.exe -m scripts.local_db upgrade
# Verify connectivity using the restricted application role from .env.
.\.venv\Scripts\python.exe -m scripts.local_db verify
# Full tests against the disposable database; never the development database.
$env:CREDITIQ_TEST_POSTGRES='1'
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
Remove-Item Env:CREDITIQ_TEST_POSTGRES
# Stop the isolated cluster when it is no longer needed.
.\.venv\Scripts\python.exe -m scripts.local_db stop
```

The start/stop helper uses PostgreSQL 18 binaries at C:\Program Files\PostgreSQL\18\bin; CREDITIQ_PG_BIN can override the binary directory. The helpers target only the isolated workspace cluster and named databases. Windows sandbox execution may require approval to start or stop it. There is no autostart service.

`.postgres/local-admin.json` holds the randomly generated cluster administrator credential, while `.env` holds a different randomly generated application-role password. Both are ignored and must not be committed. The owner is an administrator of this disposable/local cluster, not a production migration-role design. The runtime role has no superuser, database/role creation, schema creation or TRUNCATE permission; immutable tables grant SELECT/INSERT only. Authentication/session authorization is implemented; application business lifecycle authorization is deferred.

For another environment, provision PostgreSQL and migration/runtime roles separately and provide operator connection settings before using Alembic. The app role is deliberately unable to apply migrations. Never run downgrade against a database containing wanted application records. Integration tests assert the isolated database name and restrict destructive round trips to creditiq_migration_test; tests skip without explicit opt-in.

See DATABASE_VALIDATION.md for actual verification and remaining limits. Schema fields are implemented; business-level JSON contracts, job lifecycle and decision transaction orchestration remain later work. `mode=RESEARCH_ONLY` and `release_ready=false` are enforced in settings and model-version storage; live policy mode is disabled by a schema constraint.

The session dependency closes sessions on exit; services explicitly manage transactions/commits. Synchronous DB work must not be placed directly in async route bodies.

See ../../BACKEND_ARCHITECTURE.md and ../../BACKEND_TODO.md for boundaries and remaining work.

Milestone 3 validation: **63 passed, one existing TestClient deprecation warning**, including 34 authentication tests against real PostgreSQL. Pip check and Alembic drift check pass. Milestone 3 is complete; no subsequent milestone implementation is included.

Installment Intelligence V1 adds owned history/analysis APIs and read-only admin views. Apply revision 20261003_0003 with the database owner/migration role before using them; runtime needs SELECT/INSERT on the four new immutable tables. Existing Lite/auth/application contracts remain unchanged. See ../../INSTALLMENT_V1_VALIDATION.md for results and ../../INSTALLMENT_ANALYSIS_ARCHITECTURE.md for exact contracts/formulas. No model retraining is needed.
