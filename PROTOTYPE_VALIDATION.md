# CreditIQ research prototype validation

3 October 2026. Scope: owned application APIs, pinned Lite inference, transactional persistence, read-only admin APIs and a connected Next.js frontend. Existing Milestones 1–3 are reused. **RESEARCH_ONLY; release_ready=false.** No model retraining or artifact modification. No deployment or production-readiness claim.

## Reconciled scope and implementation

The current user request supersedes the historical Milestone 3 stop and the original asynchronous/outbox architecture. This prototype performs one immutable submission and synchronous scoring in one SQLAlchemy transaction. No draft editing, revision endpoint, external history, complex consent, queue, outbox, manual approval/rejection or loan-officer workflow is implemented. Existing schema supports this without a migration; head remains **20261003_0002**.

Server-generated illustrative quotes use a fixed 12% annual rate, monthly amortization, no fees and an allowed term of 6–120 months. These are explicit research UI assumptions, not bank offers, affordability checks or model-trained rates. Amounts use XXX (unspecified research currency), annual income and monthly payments. Model outputs refer to the Home Credit dataset's adverse outcome with no verified fixed prediction horizon. Existing sandbox thresholds remain 0.05 and 0.15. Quality support flags are preserved and can force MANUAL_REVIEW recommendations; there is no review workflow. DECIDED database workflow status means research scoring finished, not that a real loan decision was made.

## API inventory and contracts

All existing authentication endpoints remain available and retain cookie/JWT/refresh/RBAC behavior. Request safety middleware now covers application and admin paths as well as auth; local frontend origins and Idempotency-Key are allowed for integration.

| Method/path | Request | Response/authorization |
| --- | --- | --- |
| POST /api/v1/applications | ApplicationRequest JSON; required UUID Idempotency-Key; Origin and X-CSRF-Token | 201 ApplicationView including quote and ResultView; authenticated USER owner; exact retry returns original record |
| GET /api/v1/applications | limit 1–100 (default 20), offset >=0 | ApplicationPage: items, total, limit, offset; own records only |
| GET /api/v1/applications/{id} | UUID | ApplicationView with immutable input, quote and result; owner only |
| GET /api/v1/applications/{id}/result | UUID | ResultView; owner only |
| GET /api/v1/applications/{id}/history | UUID | Chronological HistoryView array; owner only |
| GET /api/v1/admin/users | limit, offset | Paginated public user fields; ADMIN only; no credential/session hashes |
| GET /api/v1/admin/users/{id} | UUID | UserView; ADMIN only |
| GET /api/v1/admin/applications | limit, offset | Paginated ApplicationView; ADMIN only |
| GET /api/v1/admin/applications/{id} | UUID | ApplicationView with input/quote/result; ADMIN only |
| GET /api/v1/admin/statistics | none | total_users, total_applications, total_predictions; ADMIN only |

No admin POST/PATCH/DELETE business routes exist. ADMIN is also denied POST /applications through the user route; only USER may submit. Admin role alone grants these read-only views; existing enumerated future write permissions do not expose any write endpoints. User endpoints always filter by the signed-in owner, including when used by an administrator. Unknown/nonowned IDs yield 404; unauthenticated requests yield 401, wrong roles/CSRF 403, payload errors 422, conflicting idempotency keys 409 and disabled model 503. Operational failures roll back; they never become rejection recommendations.

ApplicationRequest fields: age_years (18–100), employment_type (canonical enum), required-nullable years_employed (0–age), annual_income (positive, <=100000000, two decimal places), requested_amount (1000–10000000, two decimal places), term_months (integer 6–120), education_level (canonical enum), household_size (integer 1–30), dependent_children (integer >=0 and <household_size), optional occupation/housing_status (canonical enums or null), research_acknowledged=true. Extra fields—including applicant IDs, monthly payment, probability or privileges—are rejected. See app/schemas/applications.py/OpenAPI for exact enums. Limits are prototype input bounds, not production product eligibility.

ApplicationView: id, user_id, requested_amount, currency, status, created_at, version; detail includes input, quote and result. ResultView: prediction_id, probability, risk_score, risk_band, credit_health_index, recommendation, decision_status=NOT_A_LENDING_DECISION, model_version, scored_at, quality_flags, currency=XXX, mode=RESEARCH_ONLY, release_ready=false. Result timestamps serialize consistently in UTC. HistoryView: id, event_type, created_at, details. Lists contain summary fields without fetching every result.

## Model integration and database transaction

- Only run **20261002T140817Z-045430a7** is loaded from the existing trusted local bundle; latest.json is not used to silently change releases.
- Startup verifies every registered artifact checksum, all 14 source-module hashes, the 17-feature ordering, Lite variant/schema, currency, research flags and key dependency versions. Serialized model identity is checked against metadata. One loaded model is reused per process, with one prediction lock and one estimator thread.
- Existing creditiq_ml.contracts.request_features, CreditRiskModel.score_request, fitted preprocessing, sigmoid calibration, support flags and sandbox DecisionPolicy are reused. No new feature pipeline or training call exists. Missing feature values persist as JSON null.
- The serialized ProbabilityCalibrator lives in creditiq_ml.train, so its existing imports require matplotlib/Optuna/XGBoost even though those training paths are never executed. These dependencies are pinned in the isolated API environment; the ML environment is unchanged.
- User row locking serializes same-user submissions. Application ID is deterministically derived from user ID and the UUID idempotency key. Payload fingerprints distinguish exact retries from conflicting reuse. Account/session validity is rechecked inside the transaction.
- One transaction registers/validates the immutable research model/policy identity and writes application, immutable input version, server quote, feature snapshot, synchronous scoring job, calibrated/raw prediction, risk record, recommendation, history and audit event; it updates the application's current decision pointer. Any failure—including response assembly after persistence—rolls everything back.

Tables read/reused: users, user_profiles, auth_sessions. Submission tables: loan_applications, application_versions, loan_quotes, feature_snapshots, model_versions, scoring_jobs, predictions, risk_scores, policy_versions, decisions, application_history, audit_events. Model/policy registration is conflict-safe and verifies existing registry identity. No additional tables, indexes, migrations or trigger changes. No source/consent rows are fabricated when no external source is fetched. The browser talks only to FastAPI, never directly to database tables.

## Frontend inventory and integration

Next.js 15.5.27, React, TypeScript and Tailwind. Routes: /login, /register, /dashboard, /applications/new, /applications, /applications/{id}, /applications/{id}/result, /profile; /admin/login, /admin, /admin/users, /admin/users/{id}, /admin/applications, /admin/applications/{id}, /admin/statistics. Shared catch-all App Router entry renders these explicit workspace views; unknown routes show a not-found message.

User pages include forms, loading/error/empty states, paginated own records, quote/result/timeline views and profile. Admin pages expose only read actions. Responsive layout supports mobile and desktop. No animations, model management, advanced SHAP or lending action controls.

Same-origin /api proxy rewrites to FastAPI. Cookies remain HttpOnly; no tokens in localStorage. Mutations obtain current signed CSRF, and Web Locks serialize cookie mutation/refresh across supported browser tabs (an in-tab queue remains the fallback). After expired access, /me is rechecked under the lock before a single refresh; failures do not retry an opaque refresh blindly. Protected pages check /me and role; backend checks remain authoritative. Form retries preserve the idempotency key while the payload remains unchanged. Modern browsers with Web Locks are recommended for multi-tab use.

## Supabase boundary

Supabase PostgreSQL is the intended deployed database, using the existing SQLAlchemy/Alembic schema and PG_* connection settings. No Supabase Auth replacement or browser Supabase SDK. Use provider direct or session-mode connection settings and TLS when that separate connection milestone is authorized. No Supabase instance/credentials were supplied or contacted; remote connectivity, schema application and provider role grants are **not verified**. This session creates no deployment scripts or infrastructure automation.

Reference: [Supabase PostgreSQL connection modes](https://supabase.com/docs/guides/database/connecting-to-postgres) and [SQLAlchemy integration](https://supabase.com/docs/guides/troubleshooting/using-sqlalchemy-with-supabase-FUqebT). The local existing test cluster was restarted solely for validation after it was found stopped; no new local PostgreSQL setup was performed.

## Validation results

- Final backend full suite: **79 passed, 1 pre-existing Starlette TestClient/httpx deprecation warning, 112.24 seconds**. Includes original 63 plus 16 new cases (parametrized invalid-input cases count individually).
- Covers real champion scoring/persistence, ownership, result/history retrieval, exact idempotent retries/conflicts, concurrent duplicate submission, read-only admin access, unauthenticated/invalid requests, CSRF integration, disabled model, checksum rejection and both early/late transaction rollback. Previous auth/migration integrity regressions pass.
- TypeScript typecheck passed; Next production build passed. Initial lock typing error was fixed before the successful build.
- pip check: no broken requirements; backend lock refreshed.
- Browser tests: **3 passed in 24.8 seconds**, headless Edge against the actual built frontend, FastAPI, real Lite model and disposable PostgreSQL. Covers register/login, real submission/result/history/profile, expired-access refresh, role guards/logout, admin users/applications/statistics and mobile required-field/viewport behavior. Harmless Node NO_COLOR/FORCE_COLOR warning. Desktop/mobile screenshots visually inspected.
- Final read-only verification: all 9 artifact and 14 ML source hashes unchanged, latest pointer/research flags intact; no development schema drift at 20261003_0002; development users and applications both zero.

Early failures: stopped test database caused setup timeouts; starting the existing cluster restored connectivity. Equivalent database/session timezones serialized differently; UTC result serialization fixed the response consistency issue. Neither issue was hidden by weakening tests. Initial browser tests also found a select-label association issue, corrected in the frontend; admin browser fixture setup was made independent of the user test.

Run backend tests from services/api with CREDITIQ_TEST_POSTGRES=1 and `.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider`. Run frontend checks from apps/web with npm run typecheck, npm run build and npm test. Browser tests require the test-only backend at port 8000, Next at 3000 and the disposable test-admin fixture described in apps/web/README.md. Do not run destructive database tests concurrently with browser tests. Browser tests create only disposable test-database records; no development users are seeded.

## Reproducing browser fixtures

Browser test fixture preparation (Python, run from services/api in the API environment before starting test servers):

```python
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from scripts.local_db import owner_url, grant_application_access
from app.services.users import create_user
engine = create_engine(owner_url('creditiq_migration_test'))
with engine.begin() as connection:
    assert connection.scalar(text('select current_database()')) == 'creditiq_migration_test'
    grant_application_access(connection)
with Session(engine, expire_on_commit=False) as db:
    create_user(db, email='browser-admin@example.com',
                password='Research browser test password 2026!',
                full_name='Browser Administrator', role='ADMIN')
engine.dispose()
```

The password is an intentionally public test credential, never an operational credential. Start the API with process-local CREDITIQ_PG_DATABASE=creditiq_migration_test and CREDITIQ_AUTH_ACCOUNT_LIMIT=100, then run the frontend and browser tests. Stop the test servers before running the backend suite to clear disposable fixtures. These commands do not provision a database or modify development records.

## File-by-file change summary

| File | Change |
| --- | --- |
| services/api/app/schemas/applications.py | New strict application DTOs, response schemas and UTC timestamp serialization |
| services/api/app/services/lite_model.py | New read-only pinned loader, compatibility/hash validation and existing ML adapter |
| services/api/app/services/applications.py | New owner-scoped retrieval, illustrative quote, registry reuse and atomic/idempotent submission |
| services/api/app/routers/applications.py | Five new authenticated owner endpoints |
| services/api/app/routers/admin.py | Five new ADMIN GET-only endpoints |
| services/api/app/main.py | Model startup and router wiring, version 0.4.0 and CORS integration header |
| services/api/app/core/config.py | Lite enable flag and local frontend origins; existing DB settings reused |
| services/api/app/auth/middleware.py | Existing CSRF/body-limit/no-store protection extended to new routes; token behavior unchanged |
| services/api/tests/test_applications.py | Sixteen new tests covering persistence, access, rollback, retries and checksum rejection |
| services/api/tests/test_authentication.py | Disable unrelated model loading in existing auth fixtures |
| services/api/tests/test_foundation.py | Update authorized route inventory and isolate foundation from ML loading |
| services/api/requirements.txt | Add exact existing artifact runtime dependencies |
| services/api/requirements-lock.txt | Freeze tested backend/inference environment |
| services/api/.env.example | Document Lite enable flag, frontend origins and reuse of PG settings for remote PostgreSQL |
| services/api/README.md | Current prototype pointer and scope/validation update |
| apps/web/package.json | New frontend dependencies and build/test scripts |
| apps/web/package-lock.json | Resolved frontend dependency lock |
| apps/web/tsconfig.json | Strict TypeScript configuration |
| apps/web/next-env.d.ts | Next-generated type references |
| apps/web/next.config.ts | Same-origin API proxy to configurable backend origin |
| apps/web/postcss.config.mjs | Tailwind PostCSS integration |
| apps/web/.env.example | Backend origin example, no credentials |
| apps/web/app/layout.tsx | Shared metadata and stylesheet |
| apps/web/app/globals.css | Responsive research workspace, forms, tables and auth layouts |
| apps/web/app/[[...path]]/page.tsx | Shared route entry |
| apps/web/components/workspace.tsx | All requested user/admin pages and route protection |
| apps/web/lib/api.ts | Cookie/CSRF client, serialized refresh and typed errors |
| apps/web/playwright.config.ts | Headless Edge browser test configuration |
| apps/web/tests/prototype.spec.ts | Browser user/admin/mobile journeys |
| apps/web/README.md | Local run instructions, routes, auth flow and test boundary |
| .gitignore | Ignore frontend dependencies/build/browser outputs |
| PROJECT_PROGRESS.md | Current scope and completed/remaining evidence |
| BACKEND_TODO.md | Current prototype checkpoint and scope exclusions |
| BACKEND_ARCHITECTURE.md | Synchronous serving, transaction and frontend integration reconciliation |
| PROJECT_STATUS_REPORT.md | Prototype status and explicit remote/production limits |
| PROTOTYPE_VALIDATION.md | This API/schema/file inventory and validation report |

## Remaining work and stop boundary

Requested implementation and validation are complete: 79 backend + 3 browser tests = 82 passed, zero final failures. Test servers are stopped and browser fixtures were cleared by the final backend suite. Stop here. Connecting the finished prototype to Supabase and deployment remain separate unperformed work. Production readiness, verified monetary/target semantics, Full models, real Lite SHAP, recovery/MFA/notifications, manual reviews, CI/CD and advanced dashboards remain intentionally outside this request. Keep RESEARCH_ONLY and release_ready=false.
