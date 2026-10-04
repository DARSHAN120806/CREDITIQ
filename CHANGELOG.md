# CreditIQ ML remediation changelog

## Admin Model Research Dashboard — 4 October 2026

- Added a read-only admin dashboard comparing the pinned Lite baseline and FULL_RESEARCH_V1_NO_EXT research candidate using existing paired metrics, reliability bins, SHAP rankings, ablations, feature contracts, and model metadata.
- Added `GET /api/v1/admin/model-research`, protected by existing admin RBAC. It validates latest run pointers and reads saved reports with standard-library JSON/CSV readers; it never loads or executes an estimator.
- Added responsive calibration and ablation charts, top-20 SHAP visualization, contract groups, artifact registry, and research limitations. Captured desktop/mobile screenshots and documented sources, metrics, test results, and limitations in `MODEL_RESEARCH_DASHBOARD_REPORT.md`.
- No model artifacts, contracts, training paths, prediction endpoints, authentication behavior, migrations, or persisted data were modified. No retraining occurred; `mode=RESEARCH_ONLY`, `release_ready=false`.

## Borrowing Planner V1 + Loan Recommendation Engine V1 — 4 October 2026

- Implemented `POST /api/v1/planner/plan` for authenticated users, with strict INR inputs and optional owner-checked application reference. The service is stateless, uses Decimal for monetary arithmetic, and performs no model inference or persistence.
- Added amortizing EMI (including zero APR), repayment/interest, current debt burden, optional gross-income DTI, take-home payment ratio, residual and goal-adjusted residual, EMI headroom, savings buffer, 0/10/20/30% income stress cases, and a componentized Planning Fit Score.
- Added editable-term scenario generation and deterministic LOWER_EMI, LOWER_TOTAL_INTEREST and BALANCED ranking with normalized monthly-room/interest-saving scores, budget-fit handling, tie-breaks and human-readable reasons.
- Added a user Borrowing Planner page with cash-flow inputs and summary, ranked scenario comparison, stress test table and responsive screenshots. It remains visually and analytically separate from Lite risk, Financial Health Score and Installment Intelligence.
- Added API and validation documentation plus backend and browser tests. Lite model/artifacts, Installment Intelligence, auth behavior, model serving, migrations, prediction APIs and release flags remain unchanged (`mode=RESEARCH_ONLY`, `release_ready=false`).

## FULL_RESEARCH_V1 — 4 October 2026

- Added separate 28-feature application-snapshot research contract and reproducible dataset builder. Reuses the existing application adapter for the 17 Lite features; adds normalized external application scores/missing indicators, three non-overlapping inquiry windows, inquiry-data missingness and loan-to-goods-price ratio.
- Audited all 43 existing Full history candidates and excluded them because their historical availability, customer/account mapping, payment identity or effective installment schedule cannot be established from supplied sources. Individual definitions, decisions, measured missingness/coverage and quality notes are delivered in the feature inventory; excluded aggregate missingness remains N/A rather than fabricated.
- Generated dataset and reports for 278,220 eligible applications. No model training or production integration. Readiness report documents assumptions, leakage/fairness limits and LightGBM/XGBoost/CatBoost/Random Forest research plan.
- Existing Full and Lite code/artifacts, Installment Intelligence, APIs, database schema and raw inputs remain unchanged; research mode retained and release_ready=false.

## Full dataset preparation — 4 October 2026

- Added ml/tools/full_dataset.py outside the pinned package: existing gate/aggregation reuse, training-only cohort, streaming source profiles, feature coverage/distributions, checksummed manifests and blocked-output handling. No training or Lite changes.
- Added ml/tests/test_full_dataset.py with 9 tests; 31 targeted tests pass including existing contracts/history. Canonical normalized fixture parity, missing evidence/schedule, future payments, ownership, reproducibility, protected outputs, invalid labels and CLI status are covered.
- Produced ml/full_dataset_output/20261004-readiness-v1 reports and 278,220-row diagnostic application dataset. Real Full remains blocked (17/60 generated); no complete Full dataset was emitted.
- Added FULL_DATASET_READINESS.md; updated ML README, four tracking documents and output/test-directory ignore rules. Preserved all ML artifacts, source manifests, original CSVs and application functionality.

## Backend Milestone 3 — 3 October 2026

- Reused existing user/profile/session/audit tables for atomic registration, login, refresh rotation, logout, owned-session listing/revocation and logout-all. Added /me and CSRF bootstrap; public registration rejects privilege injection. No business/prediction/admin APIs or ML loading were added.
- Added Argon2id hashing/rehashing with bounded concurrency; HS256 JWT claim/expiry/issuer/audience validation; opaque refresh tokens stored only as SHA-256; absolute session lifetime, user-row locking, replay-family revocation and ten-device session cap. Access checks database state on every request.
- Added live User/Admin scope dependencies and trusted prompted-password admin provisioning, without public promotion. Added exact Origin and signed session-bound CSRF enforcement, HttpOnly cookies and Secure __Host- cookie support, credentialed allowlist CORS, 16 KiB auth body limit, no-store responses, redacted validation/database errors and hidden SQL parameters.
- Added shared PostgreSQL advisory-lock throttling and redacted audit records. Added three indexes in independent revision 20261003_0002, leaving initial migration/table contracts intact. Refreshed schema.sql and reused local role grants for integration tests.
- Added validated JWT/cookie/origin/rate settings and backend dependencies Argon2/PyJWT/email-validator; refreshed backend lock and local ignored secret configuration without touching the ML environment.
- Added 34 authentication test cases and updated foundation/migration expectations. Full suite: 63 passed, one pre-existing TestClient warning; pip check, runtime connectivity and Alembic drift checks passed. Development is at head 0002 with zero users. Nine ML artifact hashes, 14 source hashes, latest pointer and research flags match metadata.
- Added AUTHENTICATION.md and updated progress/TODO/architecture/status, backend README/environment example and database validation addendum. Documented CSRF/refresh client sequencing, trusted admin command and remaining operational/product work. Milestone 3 complete; mode=RESEARCH_ONLY and release_ready=false retained.


## Backend Milestone 2 — 3 October 2026

- Registered 24 SQLAlchemy Table-backed declarative models for the approved PostgreSQL schema. Added UUID/timestamptz/numeric/JSONB columns, hash/enum/finite-value checks, composite ownership/provenance FKs, scoped uniqueness and lookup/partial indexes. Composite unique names include all columns to avoid collisions.
- Added independent initial revision 20261003_0001 and schema.sql; explicitly ordered circular FK creation/removal. Database triggers protect immutable artifacts/history and completed explanations and maintain updated_at on mutable identity/application records.
- Kept backend mode=RESEARCH_ONLY and release_ready=false in typed settings and model-version constraints; policy mode allows SANDBOX/SHADOW only. Added strict environment false parsing without permitting promotion.
- Provisioned an isolated PostgreSQL 18.6 workspace cluster at loopback port 55432, development/test databases and restricted runtime role. Existing Windows instances were untouched. Ignored local data/credentials, added local operator commands, and allowed explicit Alembic connections for operator/test credentials.
- Updated foundation tests for the implemented schema; added live PostgreSQL migration/integrity/permissions tests. 29 tests pass, with one pre-existing TestClient deprecation warning; dependency consistency and Alembic drift check pass. Development revision is 20261003_0001.
- Updated all progress/TODO/architecture/status pointers, backend README and environment example; added DATABASE_VALIDATION.md. Storage tables do not implement authentication, prediction/model loading, admin APIs or frontend. ML artifact and package hashes remain unchanged.

## Backend Milestone 1 — 2 October 2026

- Added services/api foundation matching the existing design: FastAPI factory/lifespan and liveness only, typed PostgreSQL settings, SQLAlchemy declarative Base and lazy engine/session helpers, and Alembic initialization with no revisions or domain tables.
- Added independent backend dependency manifests/environment, .env.example, README and targeted foundation tests. Updated .gitignore for backend environment and local secrets.
- Added PROJECT_PROGRESS.md, BACKEND_TODO.md and BACKEND_ARCHITECTURE.md. Annotated existing design/status documents to distinguish their historical checkpoints from this foundation work.
- No authentication, prediction APIs, model loading, admin APIs, frontend or deployment implementation. Existing ML source, environment and artifacts are unchanged. See PROJECT_PROGRESS.md for final verification results and limitations.
- Milestone 1 verified: 3 foundation tests passed with one upstream TestClient deprecation warning; pip check passed; Alembic has no heads and its offline upgrade emits only BEGIN/COMMIT. Added a lock of installed backend dependencies. PostgreSQL was not provisioned or contacted; no schema migration was created or applied.

## Research-mode extension — 2 October 2026

- Added a narrow, explicit Lite-only RESEARCH manifest path in `provenance.py`, authorized by the user. It requires annual-income/monthly-annuity/unspecified-currency declarations, source/authorization references and release_ready=false. It does not falsely mark annuity frequency verified or bypass Full's source gates.
- Added the actual dataset's `adapter_manifest.json` with user assumptions and observed category/product evidence.
- `train.py` persists mode, research assumptions and the exact search budget in model metadata; adds fold/model progress logging. Existing disjoint selection/calibration/policy/test logic is unchanged.
- Added `tests/test_research_mode.py` covering the explicit research exception, rejection of implicit assumptions, prohibition of Full use and prohibition of release_ready=true.
- Appended the research authorization to DATA_VALIDATION_REPORT.md while preserving the original blocked-validation findings.
- Completed real-data Lite run `20261002T140817Z-045430a7` on 278,220 eligible labeled applicants, comparing all five model families. The bounded search uses 10,000 tuning rows and five Optuna trials per boosted-model search; final fitting uses all development rows. LightGBM with sigmoid calibration was selected on development data.
- Added `LITE_MODEL_REPORT.md`, a completion addendum to `DATA_VALIDATION_REPORT.md`, and isolated versioned models, metadata, comparison metrics and plots under `ml/real_data_output/` (ignored by Git). Added a post-fit reporting script there that verifies checksums, split separation, research flags and reloaded predictions, then produces raw/calibrated reliability diagnostics and risk-band plots without refitting.
- Validation: 45 tests passed with four upstream SHAP warnings; dependency consistency passed. Final-test ROC-AUC 0.700780, Average Precision 0.175776, Brier 0.073129. All research assumptions remain explicit and `release_ready=false`; Full source and production release gates remain open.

## 1.1.0 — 2 October 2026

Scope: C1–C5 and dependent SHAP/segmentation workflows, implementing Phase A of CREDITIQ_DESIGN.md. The existing package directory, CLI entry point, model wrapper import path, estimator factories, search grids, I/O and EDA modules are retained. No frontend, API service or database implementation was added.

### C1 — Exact model contracts

- Added `ml/creditiq_ml/contracts.py` with the exact ordered 17-feature Lite and 60-feature Full schemas, canonical category dictionaries and feature derivations.
- Required fields fail when absent/invalid; employment tenure is explicitly required-nullable. Optional occupation/housing use MISSING. Numeric infinities, invalid denominators, unsupported categories, implausible tenure and inconsistent household counts fail validation.
- Lite excludes gender, external scores, bureau history and misleading self-reported history proxies. Training includes cash-loan applicants only.
- Replaced legacy application feature generation with a Home Credit adapter that maps to the same canonical fields used by serving. Invalid rows are excluded with reasons; recursive batch validation avoids a full per-row validation loop when a few rows are bad.
- Full uses only the design's 43 history additions, with explicit statuses, units and aggregation grain. Previous applications are no longer called booked loans; current weighted card utilization is distinct from historical mean utilization.

### C2 — Training/inference parity and provenance

- The same `lite_features`, `history_features` and `validate_features` functions serve offline and request-time paths. Category normalization is explicit, without lossy punctuation sanitization.
- `CreditRiskModel._prepare` no longer silently creates absent required features. It checks schema and recomputes/checks derived inputs. Legacy pickles are rejected for inference and must be retrained.
- Added `score_request`, including UUID/version/cutoff/currency checks and matching against a trusted server quote. Full requests use raw normalized source tables and the shared history adapter, not applicant-supplied engineered aggregates.
- Added category/range/missing-tenure support flags. These are basic support checks, not a claim of complete OOD detection.
- Removed global missingness-based feature dropping and blanket numeric winsorization from supervised models. Numeric imputation stays inside each pipeline/fold; fixed one-hot vocabularies preserve column identity. Kept the existing Winsorizer for segmentation, where its fitted bounds are persisted.
- `io.py` no longer downcasts float64 monetary values before payment reconciliation.
- Added `provenance.py`: source evidence gates, source/code SHA-256 hashes, content-specific variant caches, cache-integrity checks, atomic JSON writes, versioned release resolution and checksummed trusted artifact loading.
- Added an intentionally unverified `adapter_manifest.example.json`. Real-data verification is not inferred from filenames. Original datasets and old caches are left intact.

### C3 — Installment and history correctness

- Reconcile payment events against one effective contractual schedule per loan/installment. Require the supplementary complete schedule, including never-paid items; reject unresolved schedule versions.
- Repeated identical payment IDs deduplicate safely; conflicting duplicates, missing identities, inconsistent due fields, unknown dates and unreconciled negative payments fail.
- Cumulative payments determine completion date. Count each due installment once, distinguish incomplete overdue items, include unpaid overdue durations and separate signed completion delay from positive overdue duration.
- Ignore payments/events unavailable by T and installments not yet due when measuring due performance. Never fabricate available-at dates or assume the original installment table includes every contractual obligation.
- Added unique-key checks, owner/relationship checks and future/availability filtering to history sources. Complete no-history and unavailable sources differ: zero counts are justified only by complete coverage; undefined ratios and unknown monetary totals remain null.
- Card snapshots use latest eligible rows per account; utilization retains valid values above 100%. Partial sums are not presented as complete totals. Overlapping enquiry-window totals and unverified combined cross-source account counts are removed from the model contract.

### C4 — Independent model, calibration and policy validation

- Replaced the reused 70/15/15 workflow with customer-disjoint development/calibration/policy/test partitions of 60/15/10/15. Integer rounding prevents floating-point split-size surprises.
- Lite and Full derive partition IDs from the same eligible Lite application universe. IDs and nested development fold membership are persisted.
- Nested development selection compares existing classifier families and sigmoid/isotonic calibration using separate base-fit, calibration and outer-assessment rows. Inner tuning/preprocessing stays inside base-fit data.
- XGBoost now calculates class imbalance from each fitting fold, rather than outer-training labels. Other estimator weighting remains fold-fitted. Estimator threads are bounded.
- Choose family/calibration on development Brier loss, with ROC-AUC as tie-breaker; refit the chosen base model on development and calibrator on the independent calibration cohort.
- Policy-validation predictions produce clearly non-approved diagnostic threshold tables. Only the frozen champion is evaluated on final test; no all-model test leaderboard is used for selection.
- Rename PR_AUC to AveragePrecision. Retain standard classification/probability metrics, add baseline comparisons, bootstrap intervals and band counts/observed outcomes.
- Persist immutable run directories rather than overwriting best_model.joblib in place. Publish latest.json only after successful model/report generation. Save development-only explanation/segmentation data and test predictions separately.

### C5 — Separate risk and decision policy

- Risk score remains 100×calibrated PD, with finite [0,1] validation and display-only rounding. Bands are Low <5%, Medium [5%,15%), High >=15%.
- Introduced immutable `DecisionPolicy`, ordered-threshold validation and explicit SANDBOX/SHADOW/LIVE modes. Removed F1 rejection optimization and prevalence-derived approval.
- Sandbox returns candidates, while final decisions remain MANUAL_REVIEW. Lite never automatically approves/rejects. Live policy needs Full model/version binding and independent approval evidence; unreleased, unsupported or unverified cases remain review-only.
- Automatic approval additionally requires verified affordability and product eligibility. All training artifacts remain RESEARCH_ONLY/release_ready=false; no live policy is certified or activated by training.
- Replaced the bureau-like 300–850 display transform with the design's CreditIQ 0–100 model index. Frozen reference percentiles use calibration-cohort predictions and are separate from absolute risk bands.

### SHAP changes

- Preserve LinearExplainer/TreeExplainer workflows, but explicitly identify raw-margin versus uncalibrated-probability output.
- Explain the base model; display calibrated PD separately and set calibration_explained=false.
- Derive categorical grouping from fitted encoder metadata instead of string prefixes. Record positive class, schema/model/explainer versions, reference, baseline, remainder and additivity error.
- Check output shape and additivity for every explanation. Refresh native tree baseline after evaluation, which is necessary for the tested XGBoost/SHAP combination.
- Rename misleading impact percentages to absolute attribution share. References are development-only; tree explanations explicitly identify their training-tree path reference.

### Segmentation changes

- Full-only descriptive segmentation uses development data. It no longer ranks labels using the entire labeled dataset or pretends three clusters are necessarily Prime/Medium/High Risk.
- Serialize the log transform, clipping bounds, imputation, scaling and KMeans together.
- Compare k=2..7 using sampled silhouette, repeated-seed ARI stability and minimum cluster share; fail when no acceptable candidate exists rather than force three groups.
- Evaluate descriptive segment outcomes on policy validation, not final test. Persist versioned selection evidence and model hash; test reload parity.

### CLI, environment and documentation

- `cli.py`: defaults to Lite; adds raw/output directory isolation and immutable run selection; honors --no-cache during training; validates numeric options and prohibits Lite-only segmentation.
- `all` no longer automatically performs target-informed EDA on all labeled data. Explicit EDA remains available and its exploratory limitation is documented.
- `config.py`: imports authoritative contracts and defines separate partition fractions and bounded job count. Package version is 1.1.0.
- `requirements.txt` pins direct tested dependencies; `requirements-lock.txt` captures the Windows/Python 3.12 environment. Created a project-local `.venv`; no global interpreter was replaced.
- `tests/make_synthetic.py` now generates isolated internally consistent source/schedule/event fixtures, labels them synthetic and refuses a nonempty destination.
- Added `tests/conftest.py`, `test_contracts.py`, `test_history.py`, `test_risk.py`, and `test_training.py` for contract parity, invalid inputs, partial/late/unpaid payments, source gates, cache invalidation, cohort independence, policy boundaries, all estimator families, Optuna, SHAP and serialization.
- Added `.gitignore` for environments, caches, raw data and generated artifacts.
- Replaced the short ML README with environment, manifest, normalization, testing, training, artifact and serving instructions. Added this changelog and `VALIDATION_CHECKLIST.md`.

### Compatibility and remaining release gates

Old models require retraining; their thresholds are not carried forward. Old caches do not satisfy v1 provenance. No raw real data was modified. Synthetic smoke runs validate software behavior only.

Real-data training/evaluation, evidence for monthly annuity/category/currency semantics, complete installment schedule/payment identities/availability, target horizon and population suitability, cohort acceptance and independent live policy approval remain external validation tasks. These are explicit gates, not silently filled assumptions. See the validation checklist for actual test results.
# FULL_RESEARCH_V1_NO_EXT research experiment — 4 October 2026

- Added a separate 22-feature contract and reproducible LightGBM experiment, removing exactly the three EXT_SOURCE fields and their three missingness flags from FULL_RESEARCH_V1.
- Reused the pinned Lite run's eligible applicant partitions for paired evaluation; preserved fold-fitted preprocessing, development-only tuning, separate calibration, and final-test isolation. The existing Lite model was not retrained or modified.
- Generated a training-ready dataset, model/metadata, paired ROC-AUC/AP/Brier/log-loss and calibration outputs, policy-cohort feature ablations, and Tree SHAP global importance/top-20 outputs.
- Result was a marginal point-estimate improvement over Lite (AUC +0.0040, AP +0.0006, Brier −0.00008), not evidence of meaningful improvement. Kept `mode=RESEARCH_ONLY` and `release_ready=false`; no other model families trained.
