# Milestone 2 database validation

## Milestone 3 addendum — 3 October 2026

Authentication is now implemented using the existing schema. Additive migration 20261003_0002 adds session-family, active-session-expiry and audit rate-limit indexes; no tables or original migration were replaced. Development is at 20261003_0002, Alembic detects no schema drift, and restricted PostgreSQL connectivity verifies 24 tables, RESEARCH_ONLY and release_ready=false. schema.sql was regenerated through head.

Full suite: **63 passed, one existing TestClient deprecation warning, 71.35 seconds**. This includes 34 auth cases with real runtime-role database requests, refresh replay/concurrency, atomic shared throttling, CSRF, own-session authorization and live RBAC, plus the 29 foundation/schema cases. Pip check passes. Development users count is zero; auth fixtures explicitly truncate only creditiq_migration_test, while existing schema fixtures roll back and perform their controlled migration round trip. All nine registered real Lite artifact hashes and 14 ML source hashes match metadata; latest pointer and release flags are unchanged. No training/loading occurred.

See AUTHENTICATION.md for the completed scope, client contract, tests and operational limits. No Milestone 3 blocker remains. Production security/operations and business APIs remain open. The following Milestone 2 evidence is preserved as a historical checkpoint; its statements that authentication is unimplemented are superseded by this addendum.


Date: 3 October 2026. Result: **PASS for the research database milestone**, not production readiness.

## Verified environment

- PostgreSQL 18.6, project-local data directory services/api/.postgres/data, loopback 127.0.0.1:55432.
- Development database: creditiq; schema migrated to **20261003_0001**.
- Runtime connection: creditiq_app, non-superuser; sees all **24** application tables.
- Separate disposable migration-test database: creditiq_migration_test, also at head after round-trip tests.
- The pre-existing PostgreSQL 14/18 Windows services were not changed. No external database or production environment was accessed.
- Credentials were generated, stored in ignored local files and not printed or committed. The runtime role is distinct from the isolated cluster administrator.

## Verification evidence

`CREDITIQ_TEST_POSTGRES=1 python -m pytest -q -p no:cacheprovider`: final run **29 passed, 1 warning, 4.70 seconds**. Includes the retained FastAPI foundation tests and real PostgreSQL checks. The warning is the pre-existing Starlette TestClient/httpx deprecation.

Covered:

- Upgrade, destructive downgrade to base and re-upgrade, confined to the disposable test database; repeated head upgrade is a no-op.
- All expected tables and revision stamp; no SQLAlchemy metadata drift; immutable triggers restored after round trip.
- Finite probability range, finite positive monetary amounts, paired/ordered thresholds, JSON object shape and mature-outcome requirements.
- Research-only mode and false release flag, rejection of LIVE policy, immutable model records.
- Composite application/version/owner/source references; prediction binding to matching job/model/features; scoped idempotency uniqueness.
- Current decision referencing the correct current application version; rejection of cross-application/current-version mismatch.
- Immutable prediction/version UPDATE and DELETE rejection, partial uniqueness of active model deployments, atomic transaction rollback.
- Application-role connection and denial of CREATE TABLE and TRUNCATE; liveness without a database query; no domain HTTP routes.

Additional commands/checks:

- `python -m pip check`: no broken requirements.
- `scripts.local_db verify`: database creditiq, role creditiq_app, 24 visible tables, mode RESEARCH_ONLY, release_ready false.
- Alembic `check` using an owner connection on the development database: **No new upgrade operations detected**.
- Development catalog: **89 checks, 38 foreign keys, 58 indexes** (including PK/unique indexes, excluding Alembic's table), **18 noninternal triggers**.
- Offline schema exported to schema.sql from the reviewed revision. It includes deferred circular foreign keys, named integrity constraints, indexes and immutable/timestamp triggers.
- Existing Lite artifact hashes and ML package source hashes match their original metadata manifest. ML release_ready=false and RESEARCH_ONLY status are unchanged; no retraining or model loading occurred.

## Issues found and resolved during implementation

- Windows sandbox restricted-token handling initially prevented PostgreSQL startup. An approved start of only the isolated cluster succeeded; file-based subprocess logging resolved a Windows capture-pipe hang.
- Environment string `false` initially failed Literal[False] validation. A narrow parser now accepts that false spelling and continues rejecting true/live settings.
- Composite unique constraints needed names based on every key column; the initial unpublished migration was regenerated before first application.
- Numeric Infinity is rejected by PostgreSQL numeric(20,2) with SQLSTATE 22003 before the check constraint runs. The negative test was corrected to expect that rejection; the integrity rule was not weakened.

## Limits and retained work

The database exists and accepts validated schema operations, but authentication/RBAC, HTTP business contracts, operational job/decision transitions, affordability, provider integration, prediction/model loading, frontend and deployment are not implemented. FK ownership consistency is not user authorization. JSONB shape checks do not replace future versioned input validation. Complete explanation records are immutable; pending/failed explanation state can be updated without fabricating successful numeric values.

Application runtime grants are exercised on this local cluster, not a production security certification. Production provisioning, TLS/secrets management, row-access/service permissions, backup/restore, performance/concurrency load tests and business acceptance remain open. The development cluster stays running for continued local work; stop it with the documented operator command when unused. No actual applicant, prediction or ML model registry records were seeded in the development database. Test fixtures are rolled back.
