# CreditIQ project progress

## XGBoost FULL_RESEARCH_V1_NO_EXT benchmark — COMPLETED AND VALIDATED, 4 October 2026

Report: [XGBOOST_FULL_RESEARCH_REPORT.md](XGBOOST_FULL_RESEARCH_REPORT.md). Tests, preservation checks, and screenshots: [XGBOOST_FULL_RESEARCH_VALIDATION.md](XGBOOST_FULL_RESEARCH_VALIDATION.md).

- [x] Added isolated `ml/tools/xgboost_full_research.py`; validates the same 22 fitted features, all applicant IDs/labels, exact disjoint partitions, and saved LightGBM probabilities. Reads existing artifacts only and writes to a separate XGBoost research directory.
- [x] Completed all three nested development folds for run `20261004T151458Z`; sigmoid calibration selected by development Brier (0.0733884 versus isotonic 0.0734683).
- [x] Final full-development tuning/fitting, calibrated test comparison, native Tree SHAP, model reload, and preservation hashes completed. Run output: `ml/research_output/xgboost_full_research_v1_no_ext/20261004T151458Z/`. All 42 protected artifact/contract files remained byte-identical.
- [x] Added optional read-only benchmark data to the existing admin research response and dashboard section for four metrics/deltas, ranking, calibration, and SHAP. Existing prediction/authentication/schema paths unchanged.
- [x] Full backend suite across complementary runs: 124 passed. ML/data and artifact checks: 47 passed without training other model families. Focused frontend checks: 16 passed. TypeScript and production build passed; desktop/mobile screenshots inspected.
- [x] XGBoost: ROC-AUC 0.704072, AP 0.175962, Brier 0.073083, log loss 0.266767. LightGBM is slightly better on all four point estimates. Research ranking: LightGBM first, XGBoost second; no promotion. Reports and changelog finalized. Finished model reporting can be resumed with `--resume-run 20261004T151458Z` without retraining.
- [x] Test reuse disclosed explicitly; ranking is descriptive only. `mode=RESEARCH_ONLY`; `release_ready=false`.

## Customer Segmentation V1 — IMPLEMENTED, VALIDATED, 4 October 2026

Validation details, metrics, profiles, limitations, artifact hashes, and screenshots: [CUSTOMER_SEGMENTATION_VALIDATION_REPORT.md](CUSTOMER_SEGMENTATION_VALIDATION_REPORT.md).

- [x] Built deterministic K-Means research pipeline using the pinned FULL_RESEARCH_V1_NO_EXT training data and its 22-feature contract. TARGET is excluded from fitting, selection, profiling, and descriptions; SK_ID_CURR is retained only in row assignments.
- [x] Evaluated K=2–10 using silhouette, Davies-Bouldin, and inertia; filtered clusters below 1% and selected K=4 by documented criteria. Final model fit all 278,220 rows; repeat runs reproduced assignment checksum, profiles, and metrics.
- [x] Generated the model, assignments parquet, profile CSV, metrics JSON, PCA sample, run report, and latest pointer. Saved-model reload and fixed-sample predictions verified.
- [x] Added read-only admin endpoint and `/admin/customer-segmentation` with neutral profiles, PCA, K diagnostics, methodology, and limitations. Existing admin RBAC denies ordinary users.
- [x] Full backend suite: 115 passed; browser test: 1 passed; TypeScript check and production build passed. Desktop/mobile screenshots were captured and inspected. One existing Starlette/httpx deprecation warning remains.
- [x] Lite and FULL research model artifacts/contracts, Installment Intelligence, prediction APIs, authentication behavior, schema, and migrations were untouched. No model training or lending decisions. `mode=RESEARCH_ONLY`; `release_ready=false`.

## Admin Model Research Dashboard — IMPLEMENTED, 4 October 2026

Validation and screenshots: [MODEL_RESEARCH_DASHBOARD_REPORT.md](MODEL_RESEARCH_DASHBOARD_REPORT.md).

- [x] Added admin-only `/admin/model-research` and `GET /api/v1/admin/model-research`, which reads pinned model metadata and saved comparison, calibration, SHAP, and ablation outputs. No estimator is loaded and no application scoring is possible.
- [x] Dashboard compares Lite (17 features) and FULL_RESEARCH_V1_NO_EXT (22), including paired test metrics/deltas, reliability curves, grouped feature contracts, SHAP top 20, ablations, registry, and research limitations.
- [x] Verified all nine Lite artifact checksums against metadata; none changed. No training, retraining, migrations, database writes, prediction API changes, or model artifact modifications.
- [x] Backend admin access/response tests: 16 passed; frontend TypeScript, dashboard browser/screenshot test (1 passed), and production build passed. Existing Starlette/httpx deprecation warning only.
- [x] Desktop/mobile screenshots saved under `apps/web/test-results/`. Mode remains `RESEARCH_ONLY`; `release_ready=false`.

## Borrowing Planner V1 + Loan Recommendation Engine V1 — IMPLEMENTED, VALIDATED, 4 October 2026

The prior feasibility/design-only checkpoint below is superseded. See [BORROWING_PLANNER_API.md](BORROWING_PLANNER_API.md) and [BORROWING_PLANNER_VALIDATION.md](BORROWING_PLANNER_VALIDATION.md).

- [x] Added authenticated stateless `POST /api/v1/planner/plan`, strict INR request contract, Decimal EMI/cash-flow/stress calculations, DTI only when gross income is provided, savings-goal-aware headroom, Planning Fit Score breakdown and explainable scenario ranking.
- [x] Added user-only responsive Borrowing Planner with input form, ranked scenarios, stress table, ranking rationale and cash-flow summary. Planner score remains separate from Lite risk, Financial Health Score and Installment Intelligence.
- [x] Added planner calculation, validation, ranking and endpoint tests. No ML/model, auth behavior, migrations, prediction APIs, or application data writes changed.
- [x] Frontend TypeScript check, planner Playwright journey, and Next.js production build passed. Desktop/mobile screenshots saved under `apps/web/test-results/` and visually inspected.
- [x] Full backend suite: **115 passed, zero failures** (one existing Starlette/httpx TestClient deprecation warning); no migrations were applied.
- [ ] Remains RESEARCH_ONLY and `release_ready=false`; calculations are illustrative and use unverified user-declared inputs.

## BORROWING PLANNER + LOAN RECOMMENDATION — FEASIBILITY/DESIGN COMPLETE, IMPLEMENTATION NOT STARTED, 4 OCTOBER 2026

Design documents: [PLANNER_DATASET_FEASIBILITY.md](PLANNER_DATASET_FEASIBILITY.md), [BORROWING_PLANNER_DESIGN.md](BORROWING_PLANNER_DESIGN.md), and [LOAN_RECOMMENDATION_ENGINE_DESIGN.md](LOAN_RECOMMENDATION_ENGINE_DESIGN.md).

- [x] Reviewed application inputs, Lite and FULL_RESEARCH_V1_NO_EXT contracts, eight Home Credit source schemas, current affordability formulas, user-submitted Installment Intelligence inputs/outputs, API and existing database tables.
- [x] Specified planner inputs, cash-flow/DTI and stress formulas, indicative score, scenario comparison and transparent ranking, one authenticated stateless API, and responsive UI proposal.
- [x] Confirmed Home Credit historical rows cannot fill a signed-in user's current finances; current expenses, debts, income basis, savings and goals require user entry or a future verified connection. No dataset, model, API, authentication, database or frontend behavior was modified. Retraining is not required for the proposed calculations.
- [ ] Implementation remains a future milestone. Preserve Lite, FULL_RESEARCH_V1_NO_EXT, Installment Intelligence V1, existing APIs/authentication, and `release_ready=false`.

## FULL_RESEARCH_V1_NO_EXT — TRAINED AND EVALUATED, 4 October 2026

Report: [ml/FULL_RESEARCH_V1_NO_EXT_REPORT.md](ml/FULL_RESEARCH_V1_NO_EXT_REPORT.md). Canonical isolated contract: [ml/research_contracts/FULL_RESEARCH_V1_NO_EXT.json](ml/research_contracts/FULL_RESEARCH_V1_NO_EXT.json); reproducible runner: [ml/tools/full_research_v1_no_ext.py](ml/tools/full_research_v1_no_ext.py); run output: `ml/research_output/full_research_v1_no_ext/20261004T075100Z/`.

- [x] Derived 22 features by removing only the six EXT_SOURCE fields from FULL_RESEARCH_V1; built the 278,220-row dataset and verified exact shared applicant splits with the pinned Lite run.
- [x] Trained one LightGBM research model with the established development-only selection/tuning and disjoint calibration/test partitions. Paired test: ROC-AUC 0.704740 vs Lite 0.700780; Average Precision 0.176409 vs 0.175776; Brier 0.073049 vs 0.073129. Gains are marginal, not a demonstrated meaningful improvement.
- [x] Saved calibration comparison, SHAP importance/top 20, policy-partition ablation, model and metadata. No other model family trained; Lite model, contracts, APIs and production paths unchanged. `release_ready=false`, `mode=RESEARCH_ONLY`.
- [ ] Validate source availability for all 22 features, TARGET meaning/horizon, fairness, temporal/external performance, and predeclare acceptance criteria before considering application integration.

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


## Milestone 3 — COMPLETE: authentication and authorization

3 October 2026. Milestones 1–2 are complete and preserved. Read all five tracking/validation sources; verified the existing PostgreSQL runtime connection.

- [x] Step 1: synchronize scope and inspect existing user/profile/session/audit tables.
- [x] Step 2: added strict secret/cookie/origin settings, Argon2id/JWT/signed-CSRF primitives, bounded request bodies, redacted validation errors and additive revision 20261003_0002 (three indexes only). Development upgrade succeeded; original migration preserved.
- [x] Step 3: implemented user/profile registration, login/refresh/logout, owned-session listing/revocation, logout-all, current-user response, live DB RBAC and trusted admin CLI. Added shared PostgreSQL rate limits and audit events. No application/admin business endpoints or ML loading. Integration/security validation passed in Step 4.
- [x] Step 4: 34 authentication tests and full 63-test backend suite passed on PostgreSQL (71.35 seconds; one existing TestClient deprecation warning). Alembic drift check and pip check passed; development is at 20261003_0002, with zero user fixtures.
- [x] Step 5: updated progress/TODO/architecture/status/changelog, README, environment example, dependency lock, AUTHENTICATION.md and database validation addendum; refreshed schema.sql. ML model checksum, 14 source hashes, latest pointer and research flags verified unchanged. Milestone 3 is complete; stop before business APIs.

Use existing tables; add indexes only via a new migration. No ML changes/retraining, prediction/admin business APIs or frontend. Keep mode=RESEARCH_ONLY and release_ready=false. Password recovery/email verification are separate delivery integrations, not part of the requested login/session scope.

### Milestone 3 file inventory and handoff

Created under services/api:

- app/auth/__init__.py, security.py, dependencies.py, rate_limit.py, middleware.py.
- app/schemas/auth.py, app/services/users.py, app/services/auth.py, app/routers/auth.py.
- migrations/versions/20261003_0002_auth_indexes.py, scripts/create_admin.py.
- tests/test_authentication.py and AUTHENTICATION.md.

Modified under services/api:

- app/core/config.py, app/main.py, app/db/session.py, app/db/models/schema.py (indexes only).
- scripts/local_db.py, tests/test_foundation.py, tests/test_database.py.
- requirements.txt, requirements-lock.txt, .env.example, README.md, DATABASE_VALIDATION.md, schema.sql.
- Ignored .env gained a random signing secret and local HTTP cookie configuration; no credentials are in tracked files.

Modified root tracking: PROJECT_PROGRESS.md, BACKEND_TODO.md, BACKEND_ARCHITECTURE.md, PROJECT_STATUS_REPORT.md and CHANGELOG.md.

Validation: **63 passed, 1 existing warning, 71.35 seconds**. Separate auth-only run: **34 passed, 1 warning, 59.08 seconds**. Dependency check, development schema drift check and restricted PostgreSQL connectivity passed. Additive revision 20261003_0002 applied; 24 tables preserved. Development users count is zero. No ML training or loading performed. The non-failing warning concerns Starlette TestClient/httpx deprecation. No Milestone 3 blocker remains.

Next milestone recommendation: ownership-enforced application drafts/revisions, server-owned quotes and idempotent submission with transactional/audit tests. Prediction/model loading, admin business APIs, frontend and deployment remain unstarted. Recovery/email verification, MFA and operational security remain future work. Keep RESEARCH_ONLY and release_ready=false.

The Milestone 2 and Milestone 1 sections below are historical snapshots. Their deferred-auth statements are superseded by this checkpoint.

## Milestone 2 — complete, 3 October 2026

Scope: database models/schema, constraints/indexes, Alembic migrations, migration tests and PostgreSQL connectivity only. Milestone 1 remains complete; its checkpoint below is historical.

- [x] Step 1: read/synchronize the five tracking/design documents and inspect services/api. PostgreSQL 14/18 installations found; no project .env or credentials exist. Use an isolated workspace PostgreSQL 18 development cluster, leaving installed instances untouched.
- [x] Step 2: registered all 24 approved SQLAlchemy tables; mapper configuration passes. Added typed PostgreSQL fields, named checks/indexes, composite provenance foreign keys and research-only settings/model release constraints. SQL immutability triggers will be captured in the migration step.
- [x] Step 3: created reviewed, independent revision 20261003_0001 and schema.sql. Circular foreign keys are installed after target tables; downgrade removes them first. Added immutable-record/complete-explanation/timestamp triggers. Initial development upgrade succeeded.
- [x] Step 4: PostgreSQL 18.6 connectivity verified with restricted creditiq_app role on 127.0.0.1:55432. Development schema migrated; separate test database passed upgrade/downgrade/re-upgrade and metadata drift checks. 29 tests passed (one pre-existing TestClient deprecation warning); dependency check passed. Initial Windows setup and environment boolean parsing issues were resolved.
- [x] Step 5: updated progress/TODO/architecture, status/design/changelog pointers, backend README and environment example; added database validation report and local operator instructions. Final full suite: 29 passed, one existing warning, 4.70 seconds. Development and disposable test databases both at 20261003_0001; no metadata drift. Milestone 2 is complete and work stops here.

No authentication, prediction/model loading, admin routes or frontend work is authorized. ML files/artifacts stay unchanged; backend release_ready=false and mode=RESEARCH_ONLY.

### Milestone 2 file inventory and remaining work

Created:

- services/api/app/db/models/schema.py (24 storage model classes).
- services/api/migrations/versions/20261003_0001_initial_research_schema.py.
- services/api/schema.sql (offline PostgreSQL migration export).
- services/api/scripts/__init__.py and scripts/local_db.py (isolated DB operator tools).
- services/api/tests/test_database.py and DATABASE_VALIDATION.md.
- Ignored local services/api/.env and .postgres/ database/credential/log files; no secrets added to tracked documentation.

Modified:

- services/api/app/db/base.py, app/db/models/__init__.py, app/core/config.py.
- services/api/migrations/env.py, tests/test_foundation.py, .env.example and README.md.
- .gitignore, PROJECT_PROGRESS.md, BACKEND_TODO.md, BACKEND_ARCHITECTURE.md, PROJECT_STATUS_REPORT.md, CREDITIQ_DESIGN.md and CHANGELOG.md.

Verified: 24 tables, 89 CHECK constraints, 38 foreign keys, 58 indexes (including primary/unique indexes), 18 noninternal triggers. Restricted application role connects and cannot create tables or truncate. Online upgrade, downgrade/re-upgrade in the disposable test database, schema drift, rollback and invalid data tests passed. Production remains unapproved. The isolated development cluster remains running on 127.0.0.1:55432; use the README command to stop it when unused.

Remaining: authentication/RBAC, business schema validation/transaction orchestration, application/quote APIs, model loading/prediction, explanation/admin workflows, frontend and deployment. Existing real Lite SHAP/Full-data/production ML gates remain open. Database production TLS/secret management, backup/restore, performance and deployment checks are deferred. None of this work started in this session.

Archived Milestone 1 checkpoint, 2 October 2026. PROJECT_STATUS_REPORT.md retains the preceding readiness audit with milestone addenda. No overall percentage is extrapolated from the earlier audit's approximate 45% estimate.

**Milestone 1: COMPLETE (all scoped foundation tasks verified).** Its database follow-up is now completed as Milestone 2 above; the following records the earlier foundation-only checkpoint.

## Existing ML status

- C1–C5 remediation and real Lite training/evaluation completed; last readiness audit reproduced the model and passed 45 ML tests.
- Real Lite run: 20261002T140817Z-045430a7, LightGBM with sigmoid calibration; release_ready=false.
- Real Lite SHAP outputs, Full real-data training/segmentation and production acceptance remain open. No ML files, dependencies, metadata or artifacts changed in Milestone 1.

## Milestone 1 checklist

- [x] Analyze repository and follow the existing services/api design.
- [x] Create PROJECT_PROGRESS.md, BACKEND_TODO.md and BACKEND_ARCHITECTURE.md.
- [x] Create backend package/folder structure.
- [x] Configure FastAPI application factory/lifespan and process-liveness endpoint.
- [x] Configure typed PostgreSQL connection/pool settings and environment example.
- [x] Configure SQLAlchemy Base, engine/session factory and session dependency.
- [x] Initialize Alembic configuration, environment, template and empty revisions folder.
- [x] Isolate backend dependencies from the validated ML environment.
- [x] Complete foundation verification and record results below.
- [x] Update existing status/design/changelog pointers without changing historical audit findings.

## Validation

Verified in the isolated backend Python 3.12 environment:

- `python -m pytest -q -p no:cacheprovider`: **3 passed, 1 warning in 9.62 seconds**. Checks cover liveness without database access, no domain routes/tables, typed environment settings/password handling, and Alembic offline initialization.
- `python -m pip check`: **No broken requirements found**.
- `python -m alembic heads`: **success, no revisions**, as expected.
- `python -m alembic upgrade head --sql`: **success**, outputs only BEGIN/COMMIT; no tables or database connection.
- `requirements-lock.txt` captures the installed versions, including FastAPI 0.142.2, SQLAlchemy 2.1.2, Alembic 1.20.0 and psycopg 3.3.6.

The non-failing warning is Starlette's deprecation of httpx with TestClient; it does not affect these checks. Revisit the test transport dependency in a later maintenance milestone. The initial dependency download was sandbox-blocked; the approved network retry succeeded. No dependency blocker remains.

PostgreSQL connectivity, online migrations and real schema behavior are **not validated** in this milestone; no database was created. No production claim is made. ML tests were not rerun because the ML implementation/environment was unchanged; the prior 45-pass result is historical evidence, not a new run this session.

## Files delivered in Milestone 1

Created root tracking documents: PROJECT_PROGRESS.md, BACKEND_TODO.md, BACKEND_ARCHITECTURE.md.

Created under services/api:

- README.md; .env.example; requirements.txt; requirements-dev.txt; requirements-lock.txt; alembic.ini.
- app/main.py; app/core/config.py; app/db/base.py; app/db/session.py.
- Package markers: app/__init__.py, app/core/__init__.py, app/db/__init__.py, app/db/models/__init__.py, app/routers/__init__.py, app/schemas/__init__.py, app/domain/__init__.py, app/services/__init__.py, app/repositories/__init__.py.
- migrations/env.py; migrations/script.py.mako; migrations/versions/.gitkeep.
- tests/test_foundation.py.
- Local ignored .venv directory with installed backend dependencies.

Modified existing files: .gitignore, CHANGELOG.md, CREDITIQ_DESIGN.md and PROJECT_STATUS_REPORT.md. Existing design/audit prose is preserved with clear current-progress notes. No authentication, prediction/model loading, admin, frontend or deployment code was added.

## Originally deferred at Milestone 1 (historical)

1. Database entities, constraints, initial reviewed migration and PostgreSQL integration tests.
2. Authentication, sessions, ownership and authorization.
3. Versioned applications/quotes and persisted research scoring, with explicit ML handoff acceptance.
4. Explainability and admin workflows/analytics.
5. Frontend and application reports.
6. Deployment, monitoring, operational verification and separate production gates.

The first item is now complete as Milestone 2. The remaining service/application milestones have not started.


