# CreditIQ project status and readiness audit

## XGBoost NO_EXT benchmark — COMPLETED, 4 October 2026

The 22-feature XGBoost benchmark is now trained and evaluated in isolated run `20261004T151458Z`, using the same frozen dataset and applicant partitions as LightGBM. XGBoost achieved ROC-AUC **0.704072**, AP **0.175962**, Brier **0.073083**, and log loss **0.266767**. LightGBM is slightly better on all four point estimates. No model promotion occurred; Lite remains the application baseline.

The admin Model Research Dashboard now includes XGBoost comparison, descriptive ranking, calibration, SHAP, and registry data. All 42 protected existing artifacts/contracts remained byte-identical. Validation: 124 backend tests, 47 ML/data/artifact checks, and 16 focused frontend checks passed; TypeScript and production build passed. See [XGBOOST_FULL_RESEARCH_REPORT.md](XGBOOST_FULL_RESEARCH_REPORT.md) and [XGBOOST_FULL_RESEARCH_VALIDATION.md](XGBOOST_FULL_RESEARCH_VALIDATION.md).

The shared test cohort was previously inspected; this benchmark is not independent external validation. `mode=RESEARCH_ONLY`; `release_ready=false`. The older LightGBM-only milestone below is historical and does not describe the complete current experiment inventory.

## FULL_RESEARCH_V1_NO_EXT — TRAINED AND EVALUATED, 4 October 2026

The separate 22-feature contract removes only the three EXT_SOURCE scores and their three missingness flags from FULL_RESEARCH_V1. It reuses the pinned Lite run's exact applicant partitions and compares both calibrated models on the same 41,733 final-test cases. See [ml/FULL_RESEARCH_V1_NO_EXT_REPORT.md](ml/FULL_RESEARCH_V1_NO_EXT_REPORT.md) for methodology, calibration, ablations, SHAP and limitations.

- NO_EXT LightGBM: ROC-AUC **0.704740**, Average Precision **0.176409**, Brier **0.073049**, log loss **0.266749**.
- Existing Lite on the same cases: ROC-AUC **0.700780**, Average Precision **0.175776**, Brier **0.073129**, log loss **0.267422**.
- The gains are marginal; this does not establish meaningful superiority or production readiness. No Lite artifact, production path, API, or schema changed. No non-LightGBM models were trained. `release_ready=false`, `mode=RESEARCH_ONLY`.

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


**Latest implementation update — 3 October 2026, Milestone 3 COMPLETE:** Authentication and authorization now include user registration, Argon2id passwords, JWT cookie access, rotating opaque refresh sessions, replay-family revocation, logout/logout-all, owned-session management, CSRF, shared throttling and live User/Admin permissions. 63 backend tests pass (34 auth cases), with one existing TestClient warning. PostgreSQL head is 20261003_0002; 24 tables retained, no schema drift and no development user fixtures. All nine registered Lite artifact hashes and 14 ML source hashes verified unchanged. See PROJECT_PROGRESS.md, BACKEND_TODO.md, BACKEND_ARCHITECTURE.md and services/api/AUTHENTICATION.md. No scoped blocker remains; stop after Milestone 3. Next recommended milestone: ownership-enforced application/quote workflows, before model serving. Backend mode=RESEARCH_ONLY, release_ready=false; production, ML SHAP/Full-data, business APIs, frontend and deployment gaps remain. Historical milestone statements and the earlier percentage below are snapshots, not current completion estimates.


**Historical implementation update — 3 October 2026, Milestone 2:** services/api now implements all 24 approved database tables, revision 20261003_0001, integrity/immutability rules and PostgreSQL schema export. The isolated PostgreSQL 18.6 development database is migrated and the restricted runtime connection is verified; 29 backend tests pass, including migration round trips. Database/auth-session/prediction storage exists, but authentication, prediction/model loading, admin APIs and frontend behavior are still unimplemented. Backend mode remains RESEARCH_ONLY and release_ready=false. See PROJECT_PROGRESS.md and services/api/DATABASE_VALIDATION.md. Historical percentages and “design only” findings below are retained as the original audit snapshot, not current database status.

Audit date: 2 October 2026. Scope: current local repository, source code, design documents, real-data and synthetic artifacts, metadata, reports and a fresh test run. This is a readiness assessment, not a new training run or production certification.

**Subsequent Milestone 1 update:** services/api now contains a FastAPI skeleton, environment-based PostgreSQL settings, SQLAlchemy Base/session setup and initialized Alembic without schema revisions. PROJECT_PROGRESS.md records validation and BACKEND_TODO.md records remaining work. Statements below that the backend is “not started” describe the prior audit snapshot. Database tables, authentication, prediction/model loading, admin APIs, frontend and deployment are still unimplemented. The original 45% estimate is historical; production and ML gaps remain unchanged.

## 1. Decision

**The real-data Lite model is valid and its training/evaluation milestone is complete. The entire ML phase is not yet complete. Backend development can begin for a restricted research application, with explicit remaining gates. Production lending must remain disabled.**

The immediate missing ML deliverable is SHAP output for the real-data Lite champion. Full training and real-data segmentation remain blocked by missing source semantics and normalized history inputs. Database, HTTP service, authentication, UI and deployment are designed but not implemented.

| Completion label | Current verdict | Scope and reason |
| --- | --- | --- |
| Lite research training/evaluation complete | **Yes** | Five model families compared; selected champion calibrated and independently tested; results reproduced in this audit. Bounded search and unit assumptions remain explicit. |
| Phase 1 Research Complete, covering all planned ML deliverables | **No — partially complete** | Real Lite SHAP reports are missing; Full real-data training and segmentation are absent. A narrower Lite-only research milestone can be closed after explanation validation and a documented scope decision. |
| Phase 1 Engineering Complete | **No for the full ML handoff** | C1–C5 pipeline remediation is implemented and tested, but the real explanation bundle, reproducible service packaging and serving integration verification are unfinished. This does not invalidate the completed remediation work. |
| Production Ready | **No** | `release_ready=false`, `RESEARCH_ONLY`; no approved live policy, verified production monetary/target semantics, operational service or production validation. |

Do not equate successful serialization, passing tests, or a 0.70 AUC with business acceptance. There is no recorded performance acceptance threshold that turns these results into a production release.

## 2. Completion estimate and calculation

**Estimated overall project completion: 45%.** This is an audit planning estimate for the originally requested end-to-end product including Lite and Full, not a measured fraction of effort, a delivery-time forecast, or a model-quality score. No previously agreed weighted backlog exists. The weights and partial credits below make the estimate explicit and revisable.

| Workstream | Weight | Earned points | Assessment |
| --- | ---: | ---: | --- |
| ML/system design and audit documentation | 10 | 10 | Detailed contracts, schema, endpoints, diagrams and remediation design exist; documentation has minor stale statements. |
| Shared ML contracts, preprocessing, training and remediation | 20 | 20 | C1–C5 code and dependent unit/integration tests implemented. |
| Lite real-data research package | 15 | 12 | Training, calibration, evaluation and integrity checks complete; real SHAP and formal handoff acceptance pending. |
| Full model and segmentation on real data | 10 | 3 | Algorithms and synthetic checks exist; real source validation/training blocked. |
| Database implementation | 10 | 0 | Design only. |
| Backend, auth and scoring integration | 15 | 0 | Design only; Python ML library is not an HTTP service. |
| Frontend and application reporting | 10 | 0 | Design only. |
| Deployment, monitoring and operational release | 10 | 0 | Design only. |
| **Total** | **100** | **45** | **55 points of scoped deliverables remain.** |

Backend/frontend work being unstarted is separate from whether a narrowly scoped ML deliverable is finished. Removing Full from the next release would change this denominator; it would not complete Full work.

## 3. Trained Lite artifact verification

Verified run: `20261002T140817Z-045430a7`.

Artifact directory: `ml/real_data_output/artifacts/lite/runs/20261002T140817Z-045430a7/`.

| Check performed in this audit | Result |
| --- | --- |
| Load through the existing `provenance.load_model('lite')`, with the real-data artifact root explicitly configured | **PASS**; deserialized `CreditRiskModel` with `LGBMClassifier` and sigmoid calibrator. |
| `ml/real_data_output/artifacts/lite/latest.json` | **PASS**; points to the run above, whose artifact and metadata exist. |
| Embedded model metadata versus `metadata.json` | **PASS**; exact dictionary equality after excluding the external-only `artifact_sha256` field. |
| Model's ordered feature list and schema versus metadata | **PASS**; 17 semantic Lite features and `lite-v1`. |
| Artifact SHA-256 manifest | **PASS**; all **9** listed files verified by the loader. |
| Current package source hashes versus training input manifest | **PASS**; all recorded Python source hashes match. |
| Application CSV and adapter-manifest hashes versus training manifest | **PASS**; all recorded input hashes match. |
| Reloaded predictions on all 41,733 held-out rows | **PASS**; maximum absolute difference from saved predictions is **0.0**. |
| Test metrics recomputed from those predictions | **PASS**; ROC-AUC, Average Precision and Brier match the saved report within 1e-12. |
| `test_metrics.json` versus metadata's test report | **PASS**; exact equality. |
| Comparison-table champion versus artifact | **PASS**; LightGBM + sigmoid. |
| Partition identities | **PASS**; 278,220 distinct IDs across four mutually disjoint partitions; saved test IDs match. |
| Research and decision controls | **PASS**; `synthetic=false`, `mode=RESEARCH`, `release_status=RESEARCH_ONLY`, `release_ready=false`; probabilities 0.01, 0.10 and 0.90 all produce `MANUAL_REVIEW`. |

Model file SHA-256:

```text
bc5e6cbbfe6f7d0f4418bd004ec3c471d79842387373a8b86f17266a71fcb3a2
```

Partition counts: development **166,932**; calibration **41,733**; policy **27,822**; final test **41,733**. The Kaggle `application_test.csv` is unlabeled and is not this held-out evaluation cohort.

Recomputed final-test metrics:

| Metric | Value |
| --- | ---: |
| ROC-AUC | 0.7007798513 |
| Average Precision | 0.1757755084 |
| Brier Score | 0.0731289769 |

Integrity limitations: the nine-file manifest covers model-side files, not the report directory or `metadata.json` itself. This audit additionally cross-checked metrics and metadata, but the release is not cryptographically authenticated. Local matching hashes detect inconsistency; they do not establish trusted provenance if an entire bundle is replaced. A future service needs an independently trusted release digest, restricted artifact access and explicit run selection. Joblib should load only trusted bundles.

The default `ml/artifacts` directory does not exist. Consumers must explicitly bind to `ml/real_data_output/artifacts`, and then pin the approved research run. Do not accidentally select `ml/smoke_output` or assume default configuration finds the real champion.

## 4. Report inventory

Real-data training report directory: `ml/real_data_output/reports/training/lite/20261002T140817Z-045430a7/`.

| Required output | Status | Verification |
| --- | --- | --- |
| `model_comparison.csv` | **Present** | Readable CSV; 10 rows, five model families × two calibration methods; development estimates, not ten final-test evaluations. |
| `test_metrics.json` | **Present** | Valid JSON; matches metadata; principal metrics independently reproduced. |
| `policy_validation.json` | **Present** | Valid JSON; status `NOT_APPROVED_FOR_LIVE`. Descriptive candidate-threshold evidence, not a policy approval. |
| Calibration plot | **Present** | `calibration.png`, valid 640×480 PNG. Additional `calibration_diagnostics.png` and `calibration_bins.csv` also exist. |
| ROC curve | **Present** | `roc_curves.png`, valid 640×480 PNG. |
| PR curve | **Present** | `pr_curves.png`, valid 640×480 PNG. |
| `risk_bands.csv` | **Present** | Readable CSV; 3 bands; counts total 41,733 test applicants. Additional distribution CSV/PNG exist. |
| Real Lite SHAP outputs | **MISSING** | No `reports/explain/lite/20261002T140817Z-045430a7/` outputs: `global_importance.csv`, `shap_importance.png`, `shap_beeswarm.png`, `example_explanation.json`. |

The artifact contains `explanation_background.parquet` and `explanation_sample.parquet`. These are explanation inputs, **not generated SHAP explanations**. `creditiq_ml/explain.py` implements the workflow and synthetic tests exercise its additivity/units. Existing SHAP images/JSON under `ml/smoke_output/reports/explain/full/` belong to synthetic Full runs and cannot satisfy the real Lite requirement.

Root reports present: `PHASE1_AUDIT.md`, `CREDITIQ_DESIGN.md`, `CHANGELOG.md`, `DATA_VALIDATION_REPORT.md`, `LITE_MODEL_REPORT.md`. Raw-data inspection evidence exists at `ml/reports/data_validation/validation_snapshot.json`.

Documentation gaps: `VALIDATION_CHECKLIST.md` is referenced in README/CHANGELOG but is absent. The design still opens with “implementation not started,” which describes its original checkpoint rather than the current ML package. The data report preserves an initial “no training” checkpoint and later completion addendum; read the addendum for current state. The later Lite report's next-step suggestion does not close the missing SHAP deliverable.

## 5. Completed deliverables

- C1: exact 17-feature Lite contract, canonical categories, quote validation, mandatory/nullable handling and source-to-form feature mapping.
- C2: shared training/inference feature transformations; train-fitted preprocessing; serialization and provenance; contract/parity tests.
- C3: installment-grain reconciliation, partial payments, completion dates, unpaid overdue schedule items, event identities and timing checks implemented and tested on controlled fixtures. Real Full inputs remain a separate unresolved dependency.
- C4: independent development/calibration/policy/test partitions, nested development selection, disjoint natural-prevalence calibration, and champion-only final-test evaluation.
- C5: probability-based scores and research bands, separate policy objects, version binding and safe manual-review behavior. This is implementation of policy separation, not approval of live thresholds.
- Five estimator families, grid/Optuna search, calibrated wrapper, metadata, content hashes, versioned run directories and latest pointer.
- All eight CSV files located and selected adapter columns checked; real Lite eligible cohort established under explicitly authorized annual-income/monthly-annuity/unspecified-currency research assumptions.
- Real Lite training and published research metrics, plots, band distributions, saved predictions and immutable run references.
- Fresh tests in this audit: **45 passed, 4 warnings in 47.94 seconds**, using `python -B -m pytest -q -p no:cacheprovider`. Warnings concern SHAP plotting deprecations and LightGBM SHAP output format; no failures. Tests are not a substitute for application integration/load testing.

## 6. Partially completed deliverables

| Deliverable | Implemented evidence | Remaining work |
| --- | --- | --- |
| Real Lite explainability | SHAP grouping, output units, additivity checks, development references; synthetic test coverage | Run and review explanations for the actual champion; preserve model/run linkage, review feature directions and applicant-facing wording. |
| Full model | 60-feature contract, history adapters and training path; synthetic artifacts | Resolve real data gates, validate history relationships and source completeness, then train/calibrate/evaluate on real data. |
| Borrower segmentation | Persisted transforms/scaling, evidence-based k selection and descriptive labels; synthetic validation | Real Full features, real fit and validation. Risk bands are not KMeans segments; do not label unvalidated clusters Prime/High Risk. |
| EDA/dashboard seed workflow | EDA source exists; separate structural data-validation report exists | No current real-run EDA/dashboard seed bundle located. Research EDA cannot be treated as live application analytics. Avoid outcome-driven feature selection on the already examined final test. |
| Model serving | Python wrapper and strict request/quote contract | Runtime packaging, service lifecycle, model selection, HTTP DTOs, persistence, concurrency/latency checks, error translation and secure loading. |
| Risk/decision policy | Sandbox diagnostics and enforced release gate | Approved business costs, affordability/product rules, acceptance evidence and separate policy authorization. |
| Reproducibility and handoff | Dependency pins/lock, local environment, source/input hashes | Fresh-environment reproducibility check, persisted test/checklist evidence, complete versioned report/explanation bundle and external artifact storage. |

## 7. Designed versus implemented

| Component | Design evidence | Actual implementation status |
| --- | --- | --- |
| PostgreSQL schema | `CREDITIQ_DESIGN.md` B2: tables, constraints, indexes, ER diagram | **Design only**. No ORM models, SQL schema or Alembic migrations found; no project-provisioned database evidence. |
| API contracts/endpoints | B3: `/api/v1` routes, roles, errors, idempotency, lifecycle | **Prose design only for HTTP**. ML Python input/output validation exists; no HTTP routes, generated OpenAPI or contract client. |
| Backend service | B1/B4/B5: FastAPI, services/workers and serving sequence | **Not started**. No application server, startup lifecycle, job worker or service integration tests. |
| Authentication | B2/B3: sessions, JWT, rotating refresh tokens, ownership and RBAC | **Design only**. No login/register/reset handlers, password hashing/session persistence, CSRF enforcement or authorization middleware. |
| Frontend UI | Proposed Next.js/TypeScript UI and user/admin screens | **Not started**. No Next.js project, package.json, components, routes or browser tests. |
| Deployment pipeline | Proposed monitoring, runtime isolation and rollback requirements | **Not started**. No Docker/container configuration, CI/CD workflow, infrastructure, release job or deployed environment evidence. |
| PDF/Excel application exports | Designed report jobs and endpoints | **Not started**. Offline ML CSV reports are not user/admin export services. |

The current design chooses **SQLAlchemy + Alembic** for the Python-owned database layer, replacing the earlier Prisma proposal. Do not introduce two migration owners inadvertently.

## 8. Production blockers and material risks

1. **Dataset meaning and applicability:** user-authorized source, annual-income and monthly-payment assumptions are not independently verified. Currency remains research `XXX`, target horizon is unspecified, and production-population transfer is unvalidated.
2. **Incomplete empirical acceptance:** random-split results give moderate discrimination; subgroup performance/calibration, external or temporal validation and documented acceptance criteria are absent. Five Optuna trials and at most 10,000 tuning rows are a bounded search. Reusing the final test for further selection would invalidate its independence.
3. **No approved lending policy:** policy diagnostics explicitly say not approved for live use; release is false. The model does not supply verified income/debt, affordability, eligibility rules or defensible recommended loan amounts. Lite cannot authorize automatic lending decisions under the current design.
4. **Full-source gaps:** missing normalized `DAYS_AVAILABLE`, reliable `PAYMENT_ID`, complete contractual schedule including unpaid items, source completeness/effective version evidence. Global duplicate/relationship reconciliation is unfinished. Missing payment dates/amounts also need resolution. Do not fabricate these fields from row positions or infer completeness from absent rows.
5. **Real explanation delivery incomplete:** the actual champion has no SHAP report bundle. SHAP explains the base model's raw margin for LightGBM, not the calibrated probability and not causal reasons. Synthetic evidence cannot certify the real explainer run.
6. **No application controls yet:** no authorization, persistence, immutable application lifecycle, safe exports, audit trail implementation, operational security or application integration tests.
7. **No production operations:** no service monitoring, drift/outcome feedback, rollback rehearsal, backup/restore verification, performance/load evidence or operational deployment.
8. **Local artifact handoff risks:** generated artifacts/raw data/reports are Git-ignored, with no repository evidence of external registry/backups. The report generator lives inside ignored real-data output. Report files lack checksum binding; default paths do not select the real model. Archive/version the intended bundle before handing it to another environment.
9. **Stale documentation:** missing checklist and historical status statements can lead downstream work to assume unavailable capabilities. Correct during ML handoff; this audit leaves existing documents intact.

These blockers have different scope: missing Full sources block Full, not a Lite-only research prototype; absent production evidence blocks production, not local backend engineering. No production gate should be silently removed to start development.

## 9. Recommended next milestone and implementation order

**Next milestone: “Lite research ML handoff accepted, followed by an authenticated, persisted research scoring flow.”** Begin backend foundations now; finish the real Lite explanation package before declaring ML handoff complete or delivering the explanation UI. Keep Full unavailable and every automatic decision in research/manual-review mode.

### Step 1 — Finish the ML handoff

- Generate the four missing SHAP outputs against the exact real run; inspect additivity, positive class, raw-margin units, grouped features and separation from calibrated PD. This does not require retraining.
- Record a release/checklist document identifying what is accepted for research, what is excluded from the milestone and what remains blocked. Preserve the user's assumptions and `release_ready=false`.
- Pin run ID, model and report digests, contract/schema, dependency lock and test evidence in a handoff bundle; verify load/scoring in a clean supported environment.
- Record realistic inference and explanation latency before selecting worker sizing or synchronous/asynchronous execution. Do not retune against the existing final-test results.

Suggested later SHAP command, **not executed during this audit**, from the project root:

```powershell
Set-Location 'C:\Users\darsh\Downloads\creditiq_ml_phase1\ml'
.\.venv\Scripts\python.exe -m creditiq_ml.cli explain --feature-set lite --output-dir real_data_output --run-id 20261002T140817Z-045430a7
```

### Step 2 — Database foundations

- Implement SQLAlchemy models and Alembic migrations with a single migration owner.
- First implement users/profiles/sessions, immutable applications/versions and quotes; then model/policy versions, scoring jobs, feature snapshots, predictions, risk scores, decisions, explanations and history/audit records.
- Add ownership-consistent foreign keys, money/PD bounds, uniqueness, concurrency/version checks and idempotency constraints. Test rollback, retries and transaction atomicity.
- Add transactional outbox/job persistence where the designed asynchronous flow needs it. Defer real provider/Full activation until source gates pass; retain explicit unavailable states.

### Step 3 — Backend and authentication

- Build FastAPI startup/configuration, validated request/response DTOs, errors and OpenAPI. Use the existing ML package rather than duplicate feature engineering.
- Implement registration/login/logout/refresh, password hashing, session revocation, server-side ownership and scoped admin authorization; CSRF protection where cookie authentication is used.
- Implement versioned application drafts and server-owned research quotes, submission, idempotent scoring jobs and the pinned Lite adapter. The quote's monetary domain must match the research model; an anonymized research currency cannot silently become a live local-currency quote.
- Atomically persist model/version/feature provenance, calibrated PD, score/band, manual-review recommendation and application history. Serve explanation state independently; never accept client-provided probabilities or model paths.
- Add prediction/history/explanation retrieval, review workflow and truthful dashboard counts. Test unauthorized access, stale versions, duplicate requests, model failure, unsupported categories and decision gating.
- Add Full/provider workflows, exports and richer analytics only when their dependencies are available; no fabricated segmentation or observed-default charts from predicted labels.

### Step 4 — Frontend

- Generate API types from implemented OpenAPI, then build auth/session handling and the validated application/quote form.
- Build result/history/explanation views showing the correct research label, PD/band, model version, pending/failure state and manual review. Do not call research candidate labels final approvals/rejections.
- Build admin review screens and analytics from persisted application data. Separate offline research charts from live operational counts.
- Add accessibility, validation and end-to-end user/admin tests. Defer Full segmentation, automatic eligibility/amount recommendations and export UI until matching backend capabilities exist.

### Step 5 — Delivery and operations

- Establish CI for ML checks, API/database tests and UI checks early; use tiny synthetic fixtures in CI and controlled storage for approved model artifacts.
- Build reproducible runtime images, migrations, configuration/secrets handling and a restricted research/staging environment. Verify trusted artifact retrieval and readiness checks.
- Add service metrics, privacy-aware logs, backups/restore, artifact rollback and monitoring. Test authenticated submission through persisted results in staging.
- Treat any production release as a separate approval milestone requiring resolution of section 8. Deployment success alone must never set `release_ready=true`.

### Acceptance criteria for the next milestone

1. Real Lite explanation outputs exist and are reviewed for the pinned run.
2. The documented research bundle loads and reproduces reference predictions in a clean runtime.
3. An authenticated user can submit a valid versioned research application, receive a persisted Lite score and retrieve its explanation/history.
4. Cross-user access, duplicate submissions, invalid inputs and failed model loads are tested; unsupported Full requests have an explicit unavailable response.
5. All automatic final decisions remain manual review, the UI states research limitations, and `release_ready=false` is preserved.

## 10. Audit actions and limits

Read the project inventory, design and reports; inspected ML/test workflows; loaded the existing real model; checked all recorded bundle/source hashes and exact metadata equality; recomputed held-out predictions and principal metrics; validated required CSV/JSON/PNG report readability; checked missing explanation outputs; reran the existing 45-test suite.

Only **PROJECT_STATUS_REPORT.md** was added as a persistent project deliverable. No implementation code, trained model, metadata, existing reports, thresholds or source CSVs were changed. Test fixtures used temporary locations. This audit did not rerun training, generate SHAP, provision services, rescan every history cell, establish third-party source provenance, or verify an external deployed system. An absence finding refers to this repository and its local artifacts.


## Milestone 3 — final authentication validation checkpoint (3 October 2026)

**COMPLETE for the requested authentication/authorization scope.** User/profile registration, Argon2id hashing, JWT access cookies, rotating hashed refresh sessions, replay revocation, login/logout/logout-all, owned-session management, live User/Admin RBAC, signed CSRF, shared PostgreSQL rate limits and trusted administrator provisioning are implemented.

Validation: **63 backend tests passed**, including 34 authentication cases; one pre-existing TestClient deprecation warning. Pip check, restricted PostgreSQL connectivity, migration round trips and development schema drift checks passed. Current development revision is **20261003_0002**; it adds three indexes and preserves all 24 tables and the original revision. No development users were seeded. All nine registered real Lite artifacts and 14 ML source hashes match metadata; no ML loading, retraining or artifact changes.

AUTH_VALIDATION.md contains the complete created/modified file inventory, JWT/refresh/CSRF/RBAC/session/audit architecture, exact validation evidence, known limitations and next prompt. No Milestone 3 blocker remains. Email verification/recovery, MFA, operational TLS/secrets/retention/monitoring, load/security testing and existing ML production gates remain open. Mode remains RESEARCH_ONLY and release_ready=false.

Recommended Milestone 4: ownership-enforced application drafts and immutable revisions, server-owned quotes, required consent handling and idempotent submission, with transaction/audit tests. Model loading/predictions, admin business APIs, frontend and deployment are outside that recommendation. Implementation has stopped; only documentation was changed after the user's stop instruction. Milestone 4 has not started.


