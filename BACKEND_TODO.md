# CreditIQ backend TODO

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


## Milestone 3 — complete

- [x] Read current tracking files and verify PostgreSQL.
- [x] Implement security primitives/settings and supporting indexes; revision 20261003_0002 applied to development.
- [x] Implement registration/user service, login/logout/refresh, owned-session management, role/permission dependencies and trusted administrator CLI. Integration/security tests passed.
- [x] Verify real PostgreSQL auth, CSRF, replay/concurrency, authorization and regression tests: 63 passed; one existing warning.
- [x] Record final scope, evidence, files and remaining work in tracking and AUTHENTICATION.md; stop before the next milestone.

Updated 3 October 2026. Milestone 1 remains complete. **Milestone 2 database implementation is complete**; Milestone 3 authentication is complete. No business service milestone is started.

**Historical Milestone 1 verification:** 3 foundation tests passed (one TestClient deprecation warning), pip check passed, and Alembic was empty. Milestone 2 below supersedes that database status. Dependency versions remain captured in services/api/requirements-lock.txt.

## Milestone 1 — foundation

- [x] Inspect repository and retain existing ML structure.
- [x] Create services/api with package placeholders, settings, FastAPI skeleton and liveness.
- [x] Add PostgreSQL/psycopg settings and SQLAlchemy Base/session setup.
- [x] Add Alembic environment, template and empty revision directory.
- [x] Add isolated dependency manifests and local setup instructions.
- [x] Add targeted foundation checks for liveness, settings and offline Alembic.
- [x] Run verification, capture installed dependency lock and record results.
- [x] Add architecture/progress tracking and update historical status pointers.

## Milestone 2 — database (complete)

- [x] Inspect PostgreSQL installations and provision an isolated PostgreSQL 18.6 workspace cluster (127.0.0.1:55432); create development and disposable test databases and restricted runtime role.
- [x] Implement all 24 approved SQLAlchemy storage models without authentication or prediction behavior.
- [x] Create reviewed initial Alembic revision 20261003_0001 and schema.sql export; migrate the development database.
- [x] Implement named checks/indexes, composite provenance FKs, deferred circular references and immutable-record triggers. Verify database rollback boundaries; business transaction orchestration remains later work.
- [x] Verify live application-role connection, upgrade/downgrade/re-upgrade, no schema drift, invalid-data rejection and restricted permissions on PostgreSQL.
- [x] Run 29 passing tests, retain the known TestClient warning and document validation/operations in services/api/DATABASE_VALIDATION.md.
- [x] Verify original ML artifact/source hashes and release status remain unchanged.

## Later work and completed authentication handoff

- [x] Authentication, password storage, rotating sessions, CSRF and own-session/RBAC enforcement (Milestone 3); application ownership belongs to the next business milestone.
- [ ] Application drafts/revisions, server-owned quotes and idempotent submission.
- [ ] Research-only model loading, version pinning, feature parity and persisted predictions.
- [ ] Real Lite SHAP handoff and explanation retrieval; no calibrated-PD attribution claims.
- [ ] Admin review APIs, truthful analytics and user/admin exports.
- [ ] Full routing only after independent source-data and model gates pass.
- [ ] Frontend, service integration/E2E tests, deployment/CI, monitoring and rollback.
- [ ] Verified monetary/target semantics, population validation and independent live-policy acceptance before production.

## Completion boundary

Stop after Milestone 3. Authentication is implemented and tested; no Milestone 4 code is authorized in this session. Development database is at 20261003_0002; no schema drift, 63 backend tests passed, one existing TestClient warning. No scoped blocker remains. See services/api/AUTHENTICATION.md for cookie/CSRF integration, trusted administrator provisioning and test commands.

Production provisioning, TLS/secret rotation, verified account recovery/email, MFA, audit/session retention, backup/restore, monitoring and load/security testing remain open. Existing ML gaps remain unchanged. Backend mode=RESEARCH_ONLY and release_ready=false; no model loading or retraining occurred.


