# CreditIQ backend architecture — Milestones 1–3

## FULL_RESEARCH_V1 — DATASET BUILT, RESEARCH TRAINING READY, 4 October 2026

Authoritative handoff: [FULL_RESEARCH_V1_READINESS.md](FULL_RESEARCH_V1_READINESS.md). Separate contract is [ml/research_contracts/FULL_RESEARCH_V1.json](ml/research_contracts/FULL_RESEARCH_V1.json); builder is [ml/tools/full_research_v1.py](ml/tools/full_research_v1.py). Final output directory: `ml/research_output/full_research_v1/20261004-delivery/`.

- [x] 28 reproducible application-snapshot features, explicit contract, exact per-candidate feature inventory (28 KEEP, 43 history candidates DROP), missingness/coverage/distribution reports, target counts, data risks and SHA-256 manifest.
- [x] Dataset has 278,220 eligible, unique applicants; 254,999 TARGET=0 / 23,221 TARGET=1. All rows retained; 31.87% complete-case coverage before fold-fitted imputation.
- [x] 43 existing history aggregate candidates were not generated. Their missingness is correctly recorded N/A; the feature report provides only measured raw-source row coverage as a proxy. No historical availability, schedule or payment identity was inferred.
- [x] No estimator trained. No existing Full or Lite contract/model, Lite artifacts, raw sources, Installment Intelligence, API or schema modified. `release_ready=false`, `mode=RESEARCH_ONLY`.
- [ ] Before interpreting results: verify target horizon/population, external-score source and serving access, research assumptions and fairness. Next milestone may separately train/compare LightGBM, XGBoost, CatBoost (isolated dependency), and Random Forest under the documented holdout/calibration plan.

Research contract status means suitable for a controlled model-training experiment, not production. Existing Lite performance figures do not measure this feature contract. Historical milestone sections below are unchanged.

## Installment Intelligence V1 — COMPLETE, 4 October 2026

This is the authoritative current checkpoint. Earlier sections below are historical snapshots; their Coming Soon, table-count and pending-work statements are superseded here. See [INSTALLMENT_V1_VALIDATION.md](INSTALLMENT_V1_VALIDATION.md) for the complete file inventory, API contracts, tests, commands and limitations, and [INSTALLMENT_ANALYSIS_ARCHITECTURE.md](INSTALLMENT_ANALYSIS_ARCHITECTURE.md) for implemented formulas and storage boundaries.

- [x] Reused existing installment reconciliation and aggregation without modifying ML source or artifacts; no retraining.
- [x] Added immutable import, effective schedule, payment and analysis storage; transactional writes, ownership, idempotency, constraints and indexes.
- [x] Delivered six user endpoints and three read-only admin endpoints, reusing existing authentication, CSRF and RBAC.
- [x] Delivered repayment discipline, reliability, on-time percentage, delays, recovery, consistency, missed/late counts, coverage and recent improvement calculations with explicit insufficient-data states.
- [x] Added manual and JSON history entry, labeled demo data, saved history, responsive charts, accessible chart tables and dashboard integration. User page: /financial-analysis. Admin page: /admin/installments.
- [x] Full validation: **101 backend tests + 19 frontend tests = 120 passed**, zero final failures. Next production builds and final standalone TypeScript check passed. Desktop/mobile screenshots generated and visually inspected in docs/screenshots/installments-v1. Existing non-failing TestClient/httpx and Node color-environment warnings remain.
- [x] Local PostgreSQL revision **20261003_0003** applied; **28 mapped tables and 18 immutable triggers**. Disposable migration upgrade/downgrade/reupgrade and schema-drift checks passed. Existing migrations preserved.
- [x] Final cleanup: disposable test users = 0; milestone test servers on ports 13000/18000 stopped. Development data preserved: 2 users, 3 applications and 1 installment import at final verification. Pre-existing user servers were not stopped.
- [x] Pinned Lite run 20261002T140817Z-045430a7 loads successfully; all 9 artifact and 14 ML source checksums match. Existing application prediction flow, authentication behavior and API contracts remain working. Admin remains read-only.

Backend remains mode=RESEARCH_ONLY and release_ready=false. Supabase configuration is unchanged; no remote migration or deployment was performed. Applying revision 0003 and appropriate runtime table grants to a deployed database remains a separate rollout task.

No scoped implementation or test blocker remains. Input completeness is self-declared; history is retrospective, not certified historical evidence for Full-model inference. Demo data is explicitly separated. V1 does not import raw Kaggle history, verify bank feeds, train a new model, or change approval decisions. Corrections require a new immutable import.

Recommended next milestone: Full-history data feasibility and feature-contract reconciliation before any separately authorized model experiment. Do not reimplement this milestone or retrain the pinned Lite model. Restart existing application processes if needed to load saved changes.

## Phase 2 consumer UI and financial insights — COMPLETE, 3 October 2026

Synchronized with the saved checkpoint; continued existing implementation without recreating completed milestones. All requested Phase 2 UI work is complete and validated. See [UI_PHASE2_REPORT.md](UI_PHASE2_REPORT.md) for the file-by-file inventory, formulas, limitations and screenshot evidence. The historical sections below describe earlier states; this section is authoritative for current Phase 2 status.

- [x] Consumer wording, shared INR display-only formatting and probability-based Low/Moderate/High labels.
- [x] Financial Health Score, four dashboard cards, three Recharts charts, all-page analytics and financial summary.
- [x] Rich application history, responsive teal styling, affordability insights and illustrative loan ranges.
- [x] Financial Analysis Coming Soon page and empty schema placeholder; architecture documented, no analysis functionality or migration.
- [x] Fixed mobile overflow caused by hidden table accessibility text, keeping the accessibility label and scrollable table.
- [x] Corrected the database test's obsolete empty-development-users assumption. Permissions are checked read-only; the existing account is preserved.
- [x] Full backend suite: **79 passed in 145.86s**. Frontend suite: **16 passed in 2.2m** (13 helpers + 3 browser journeys). **95 total, zero final failures**. Existing non-failing TestClient/httpx deprecation and Node color-environment warnings remain.
- [x] Final Next production build passed, including TypeScript validation. Five screenshots saved and visually inspected in docs/screenshots/phase2.
- [x] Nine artifact hashes and fourteen ML source hashes match; pinned run/latest pointer unchanged. No retraining, artifact edits, authentication/API behavior changes or Supabase configuration changes.
- [x] Schema remains 24 mapped tables, revision 20261003_0002; no Alembic drift. Test servers stopped and disposable test fixtures cleared. Development users preserved: 1. Existing PostgreSQL left running.

Backend remains mode=RESEARCH_ONLY and release_ready=false. Admin remains read-only. INR and risk labels are frontend presentation; original amounts, currency, probabilities and decision recommendations persist unchanged. Affordability uses the saved EMI; range estimates use 12% annual interest and selected term, excluding other debts/expenses/fees. Data hydration uses four concurrent detail requests and all list pages; future aggregate endpoints can improve large-history performance.

Remaining: future installment analysis implementation only if requested; deployed Supabase verification and deployment remain outside this phase. No Phase 2 validation blockers remain. Resume by reading this section and UI_PHASE2_REPORT.md; do not reimplement Phase 2 or retrain models.

## Research prototype expansion — COMPLETE, 3 October 2026

The user's current request supersedes the earlier stop-at-Milestone-3 boundary. Reuse all completed schema/authentication and deliver synchronous Lite application submission, owned reads/results/history, read-only admin APIs and a Next.js frontend. No deployment, retraining, ML artifact edits, manual review workflow or production hardening.

Completed implementation: pinned model loader with metadata/source/artifact/runtime validation; shared existing ML transformations; 17-feature snapshots; immutable input/quote/prediction/risk/recommendation/history records in one transaction; user-scoped idempotency and ownership; ten requested APIs; Next.js user/admin pages and cookie/CSRF integration. No migration is needed; revision remains 20261003_0002. The only auth integration change extends request safety middleware to application/admin paths and allows local frontend origins/Idempotency-Key CORS header.

Validation complete: **79 backend tests passed (112.24 seconds), 3 browser tests passed (24.8 seconds), 82 total; zero final failures**. One existing Starlette TestClient/httpx warning and a harmless Node color-environment warning remain. TypeScript, Next production build and pip check passed. All 9 artifact hashes and 14 ML source hashes, latest pointer and research flags remain unchanged. No schema drift; development has zero users/applications. PostgreSQL revision remains 20261003_0002. Test API/frontend servers were stopped; disposable browser fixtures were cleared by the final backend suite. The pre-existing local PostgreSQL test cluster was restarted solely for validation. Supabase connection/deployment remains unperformed; no credentials were supplied.

Research simplifications: fixed illustrative 12% annual quote, no fees, XXX currency; server-derived monthly payment; one submitted immutable version per POST, with atomic scoring and no outbox. Existing model policy produces sandbox recommendations only. Admin routes are GET-only and require ADMIN role; submitting through the user POST endpoint also rejects ADMIN accounts. Manual-review recommendation text is not a queue. Source consent tables are unused because no third-party history is fetched. Keep RESEARCH_ONLY and release_ready=false.

All requested application APIs, model integration, admin read views and frontend pages are complete and tested. Stop here; no next milestone has started. PROTOTYPE_VALIDATION.md contains the file-by-file inventory, exact API/request/response contracts, database usage, model integration details, commands, evidence and remaining exclusions. Frontend instructions: apps/web/README.md. Historical pending draft/review/Full/explainability/deployment tasks below are not part of this completed research scope.

Current deliverables:

- [x] POST applications with atomic immutable submission, server quote and real Lite prediction.
- [x] Own application list/detail/result/history and idempotent/concurrent retry handling.
- [x] Five ADMIN read-only APIs, user/admin permissions verified.
- [x] User login/register/dashboard/form/history/details/result/profile and admin login/dashboard/users/applications/statistics pages.
- [x] Cookie/CSRF/session persistence and role-aware frontend routing.
- [x] Backend/browser/build/type/integrity validation and final documentation.
- [ ] Separate future work: supply and verify Supabase connection/schema grants, then independently authorize deployment. No deployment files or infrastructure automation created.

Historical checkpoints below remain records of earlier milestones.


**Final stop checkpoint — 3 October 2026:** Milestone 3 is complete. Implementation stopped by user instruction; this update is documentation only. AUTH_VALIDATION.md records the full file inventory, architecture, security/session contracts, migration history, test evidence, limitations and recommended Milestone 4 scope. Final backend result: 63 passed, one existing warning; current revision 20261003_0002. No new tests or implementation changes after the stop instruction. No Milestone 4 work started; ML unchanged, RESEARCH_ONLY, release_ready=false.


## Milestone 3 implemented (complete, 3 October 2026)

Implementation checkpoint: the security and service/route layers now exist. The public registration body forbids role/permission fields and gives the same 202 acknowledgement for duplicate addresses. Administrator creation is an explicit trusted CLI action with prompted password and enumerated scopes, never a public role-switch endpoint. Auth bodies are capped at 16 KiB, sensitive responses are no-store, validation errors omit submitted values, and SQL parameter logging is hidden. Only three indexes were added in revision 20261003_0002; all 24 tables and the original migration remain intact. Real PostgreSQL adversarial/concurrency tests pass: 34 authentication cases, 63 backend cases overall; no schema drift at revision 20261003_0002.

Reuse the existing users, user_profiles, auth_sessions and audit_events tables. Add only session-family and audit-throttle lookup indexes through a separate migration. Passwords use Argon2id; access uses short-lived HS256 JWT HttpOnly cookies; refresh tokens are opaque random values with SHA-256-only storage. Rotation retains revoked rows for replay detection; PostgreSQL user-row locks serialize family mutation. A replay revokes the complete family. Access requests check current session/account state and current DB role/permissions. Signed session-bound double-submit CSRF plus an explicit Origin allowlist protect cookie mutations, including login/registration. PostgreSQL advisory locks and audit records provide rate limits shared across workers. Services are synchronous with explicit transactions; no new business APIs or ML integration.

Updated 3 October 2026. This document describes implemented foundations and database schema separately from later service design. CREDITIQ_DESIGN.md remains the domain/ML design reference. PostgreSQL persistence has one owner: SQLAlchemy with Alembic, not Prisma.

## Repository findings and layout

Before Milestone 1 the repository contained root design/audit reports and an existing ml/ package with tests, local datasets and model artifacts. No service, database migration tree or frontend was present. The existing ML directory and artifacts are preserved. The backend is services/api, matching the prior proposed layout; no duplicate backend/ directory is introduced.

```text
services/api/
  .env.example
  requirements.txt
  requirements-dev.txt
  requirements-lock.txt
  README.md
  alembic.ini
  app/
    __init__.py
    main.py
    core/config.py
    db/base.py
    db/session.py
    db/models/__init__.py
    db/models/schema.py # 24 Table-backed declarative models
    auth/             # password/JWT/CSRF, DB authorization, middleware, rate limits
    routers/auth.py
    schemas/auth.py
    domain/           # empty package for later domain rules
    services/users.py
    services/auth.py
    repositories/     # empty package for later persistence operations
  migrations/
    env.py
    script.py.mako
    versions/.gitkeep
    versions/20261003_0001_initial_research_schema.py
    versions/20261003_0002_auth_indexes.py
  schema.sql
  scripts/local_db.py
  scripts/create_admin.py
  AUTHENTICATION.md
  DATABASE_VALIDATION.md
  tests/test_foundation.py
  tests/test_database.py
  tests/test_authentication.py
```

The ignored services/api/.venv is independent of ml/.venv. Package __init__.py files also exist in core and db. Placeholder packages have no business behavior.

## Implemented flow

Environment/service .env -> typed Settings -> create_app -> FastAPI lifespan -> lazy PostgreSQL engine + session factory -> dispose engine at shutdown.

GET /api/v1/health/live reports process liveness without querying the database. Authentication routes additionally provide CSRF bootstrap, registration, login, rotating refresh, logout, logout-all, owned sessions and /me. See services/api/AUTHENTICATION.md for the exact HTTP contracts. No lending endpoints exist. Swagger/ReDoc/OpenAPI are development inspection tools, not implemented business contracts. No readiness endpoint claims database or model availability.

Configuration builds a structured SQLAlchemy URL using postgresql+psycopg. This preserves special characters in passwords and avoids embedding credentials in Alembic INI text. Port/pool limits are checked, and password representations are masked. Secrets remain in environment variables or an ignored local .env. Milestone 2 provisioned an isolated local PostgreSQL 18 cluster, development and migration-test databases, and a restricted app role. This is not deployment automation.

The SQLAlchemy DeclarativeBase uses a constraint/index naming convention, with all composite unique columns represented in names. Its metadata now registers 24 approved tables through app/db/models. Request session setup closes the session and leaves explicit transactions to services; the authentication services now implement their own commits/rollback and locking. The selected synchronous engine remains unchanged; use synchronous endpoints/dependencies for blocking DB work, and evaluate worker/async requirements when real workloads exist.

Alembic imports the same Settings, Base metadata and model registration package. Offline mode generates SQL without a connection; online mode uses a short-lived NullPool engine and disposes it, or accepts an explicit operator/test connection. Initial revision 20261003_0001 contains frozen operations independent of live models. It and additive index revision 20261003_0002 are applied to the isolated local development database. Migrations remain explicit operator actions, never application startup side effects.

## Implemented database contracts

All 24 B2 tables are implemented: users, user_profiles, auth_sessions, loan_applications, application_versions, loan_quotes, data_consents, source_snapshots, feature_snapshots, feature_snapshot_sources, model_versions, model_deployments, scoring_jobs, predictions, risk_scores, policy_versions, decisions, explanations, segment_assignments, reports, application_history, loan_outcomes, audit_events and outbox_events. Authentication behavior now uses these existing tables; prediction services remain unimplemented.

UUID primary keys, timezone-aware timestamps, numeric(20,2) amounts, JSONB shape checks, hash formats, enum-like CHECK constraints, finite PD/amount checks, scoped uniqueness and lookup/partial indexes implement the approved storage design. Composite foreign keys bind application versions to owners/consents, source-feature provenance, job/model/feature predictions, and current decisions. Deferred circular FKs let an application and first immutable version be inserted atomically; the current decision must be cleared or replaced when its current version changes. Session ownership/RBAC is implemented; application-level ownership and complete business JSON contract semantics remain future work.

Version/snapshot/prediction/risk/policy/decision/history/audit records have database mutation-rejection triggers; the migration lists all 14 protected tables. Successful explanations are frozen, while incomplete explanation workflow rows remain mutable. Mutable users/profiles/applications get updated_at triggers. There is no cascading deletion of decision history. Retention/purge workflows require a later explicit design.

Additive implementation details beyond the conceptual field list are deliberate: users.permissions stores explicitly assigned administrator scopes; scoring_jobs.request_body_hash supports later idempotency conflict detection; redundant application/variant identity columns enable composite FKs; model_versions.mode/release_ready are constrained to RESEARCH_ONLY/false. Policy modes are limited to SANDBOX/SHADOW for this research milestone; enabling LIVE requires a future reviewed migration and release approval, not just a configuration change. Decision kind separates recommendations from final records; actual approved/rejected records require an actor, with actor authorization left to future services.

An isolated loopback PostgreSQL cluster uses port 55432. Its administrator runs migrations; creditiq_app has DML only, no schema creation/TRUNCATE and no UPDATE/DELETE on immutable tables. The local operator script targets this cluster only. Database schema rollback tests use creditiq_migration_test, never creditiq. See services/api/DATABASE_VALIDATION.md for test results and limitations.

The app uses FastAPI's [lifespan lifecycle](https://fastapi.tiangolo.com/advanced/events/) and [typed environment settings](https://fastapi.tiangolo.com/advanced/settings/). Alembic's [offline migration workflow](https://alembic.sqlalchemy.org/en/latest/offline.html) allows initialization checks without a PostgreSQL server.

## Explicitly deferred

Application/quote APIs, prediction APIs, ML imports/model loading, admin APIs, SHAP integration, jobs/queues, frontend, deployment and monitoring are not implemented. Future handlers must reuse the existing ML transformation package and select an approved artifact explicitly, but this milestone introduces no such integration.

The real Lite run remains a research artifact with release_ready=false. The backend's existence changes no ML acceptance gate. Database connectivity is verified locally; production security, operational controls and broader acceptance remain open. This is not production ready.

## Authentication integration and validation

Access JWTs and opaque refresh tokens are HttpOnly cookies. Secure environments use __Host- names with Path=/ and no Domain; local loopback HTTP uses unprefixed cookies. Every mutation requires signed, refresh-bound CSRF plus an exact allowed Origin. Future UI must send credentials and serialize refresh across tabs: concurrent reuse revokes the whole family by design. SameSite=Strict requires a same-site hosting topology.

USER gets profile:read, sessions:manage, applications:own. ADMIN additionally gets only assigned recognized scopes, checked live from PostgreSQL. require_role/require_permission dependencies are reusable; future application queries must enforce owner identity separately. Business side effects will need transaction-time authorization checks. Public registration cannot select privileges; scripts.create_admin is the trusted prompted-password provisioning path.

63 tests pass, including 34 authentication cases using real PostgreSQL, concurrent rotation/replay, session ownership, CSRF, rate limiting and changing permissions/status. Pip check and schema drift check pass. No development users were seeded. The original ML model hash, 14 package hashes, latest pointer and research flags remain unchanged. No Milestone 3 blocker remains. Account recovery/verification, MFA, key/secret lifecycle, retention, public-traffic load and independent security validation remain future operational/product work.


