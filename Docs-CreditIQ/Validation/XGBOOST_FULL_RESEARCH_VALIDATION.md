# XGBoost FULL_RESEARCH_V1_NO_EXT validation

Date: 4 October 2026. Status: **completed and validated**. `mode=RESEARCH_ONLY`; `release_ready=false`.

## Scope and lineage

- XGBoost run: `20261004T151458Z`.
- Frozen LightGBM baseline: `ml/research_output/full_research_v1_no_ext/20261004T075100Z/`.
- Dataset: the baseline's `full_research_v1_no_ext_train.parquet`, with the same 278,220 eligible labeled applicants and exactly the same 22 fitted feature columns in the same order.
- Applicant partitions: saved Lite run `20261002T140817Z-045430a7`, also used by the LightGBM research experiment. Sizes: development 166,932; calibration 41,733; policy 27,822; test 41,733.
- The script requires disjoint and exhaustive partition IDs, identical saved test labels, and agreement between stored LightGBM probabilities and headline metrics.
- The legacy contract's top-level `features` array is stale. The benchmark uses its 22 `feature_definitions`, cross-checked against LightGBM's fitted `feature_columns` and exact parquet schema; no existing contract is edited.

## Training and calibration

Only XGBoost predictive estimators are trained. Existing pipeline helpers provide fold-fitted preprocessing and fitting-fold class weights. Three outer development folds compare sigmoid and isotonic calibration. Each nested tuning search uses five Optuna trials and three inner folds, with the same 10,000-row bounded inner tuning sample. As in the LightGBM research script, final tuning uses the entire 166,932-row development set.

Selection uses mean development Brier, then ROC-AUC. Sigmoid was selected before test evaluation:

| Calibration | Development Brier | Development ROC-AUC | Development AP |
|---|---:|---:|---:|
| Sigmoid | 0.073388398 | 0.689722886 | 0.172984321 |
| Isotonic | 0.073468280 | 0.688338041 | 0.165843652 |

Final calibration fits only the separate calibration partition at natural prevalence. The logistic component of sigmoid calibration is reused; this is not a standalone Logistic Regression benchmark. The policy partition is preserved and unused for selection.

The test cohort has already been inspected during previous experiments. The report and dashboard disclose this reused holdout. No test metric is used to choose hyperparameters or calibration, and no deployment/promotion decision is made.

## Artifacts and preservation

Outputs are isolated under `ml/research_output/xgboost_full_research_v1_no_ext/20261004T151458Z/`. The runner records SHA-256 hashes before and after training for existing Lite artifacts, the entire frozen NO_EXT output, customer segmentation outputs, and research contracts. It saves the new estimator before reporting so an interrupted report can resume without another fit.

The model, paired predictions, four-metric comparison, calibration JSON/plot, native exact Tree SHAP importance/top-20/plot, development selection and fold lineage, report, and versioned metadata are published. The XGBoost-specific latest pointer is `20261004T151458Z`. Reloaded probabilities matched the saved test probabilities exactly. Native SHAP dimensions and additivity passed. All **42 protected files** retained identical hashes, verified again by the saved-artifact tests.

Dataset SHA-256: `31b6e5f08704568a2923e23b3254f03aba5bc1a8177342d6d27191ca4466711f`. Partition manifest SHA-256: `6cdd57d04b10ed667dc62a484daf19e44db5c5b6952b921fe088296003cb80e3`. New artifact checksums and library versions are recorded in run metadata.

Final XGBoost metrics: ROC-AUC **0.704071560**, AP **0.175962486**, Brier **0.073083080**, log loss **0.266766936**. LightGBM is slightly better on all four point estimates. The display ranking is LightGBM first, XGBoost second; there is no model promotion. See [XGBOOST_FULL_RESEARCH_REPORT.md](XGBOOST_FULL_RESEARCH_REPORT.md) for the full comparison.

## Dashboard integration

Existing admin route `/admin/model-research` and `GET /api/v1/admin/model-research` gain an optional `xgboost_benchmark` response section. Existing response fields remain intact. The loader reads saved JSON/CSV only, validates baseline lineage, and performs no estimator loading, inference, or database writes. If the benchmark is absent, the previous dashboard still renders; inconsistent published metadata returns 503.

The new section shows LightGBM/XGBoost ROC-AUC, AP, Brier, log loss and deltas; descriptive ranking by test Brier ascending with ROC-AUC descending tie-break; both calibration curves; development calibration selection; and XGBoost SHAP importance. Ranking never promotes a model. The artifact registry includes the new run. Test-reuse wording replaces the earlier claim that this is an untouched test set.

## Validation results

- Full backend suite across two complementary runs: **124 passed** (99 existing regression tests plus 25 application/admin and benchmark-loader tests). Existing admin RBAC denies ordinary users; real Lite prediction/persistence tests pass. Benchmark tests cover saved metrics/deltas/ranking, absent optional artifacts, invalid pointers, and mismatched provenance.
- Existing ML data, contract, history, risk, and research-mode tests: **45 passed**. Saved XGBoost artifact tests: **2 passed**. Total **47 passed**. Tests verify all output checksums, all 42 protected hashes, disjoint development fold lineage, exact feature order, exact test identity/label alignment, and reloaded prediction parity. Estimator-training tests were intentionally excluded so no other model family was trained for validation.
- Focused frontend tests: **16 passed** (15 existing model research/segmentation/financial checks plus one XGBoost dashboard test using actual saved benchmark values). Desktop/mobile screenshots captured and visually inspected. Browser rendering uses mocked auth/API responses populated with real saved research outputs; backend HTTP authorization and artifact loading are verified separately by backend tests. The unrelated live browser workflows were not rerun.
- TypeScript check: passed.
- Next.js production build: passed.
- `git diff --check`: passed; Git emits existing Windows LF/CRLF notices.

Warnings: one existing Starlette/httpx deprecation per backend invocation; three existing SHAP/Matplotlib pending-deprecation warnings when the reused ML helper is imported; Playwright's existing NO_COLOR/FORCE_COLOR warning. No unresolved test failure remains in the executed checks.

Screenshots:

- [Desktop benchmark](apps/web/test-results/xgboost-research-desktop.png)
- [Mobile benchmark](apps/web/test-results/xgboost-research-mobile.png)

The first ML test invocation could not access Windows' shared pytest temporary directory. A fresh workspace-local `--basetemp` resolved the fixture errors without source changes. Port 3000 was already occupied, so the production browser-test server uses port 3011; the existing server was not stopped.

## Files in this milestone

Created:

- `ml/tools/xgboost_full_research.py`
- `ml/tests/test_xgboost_research.py`
- `services/api/tests/test_model_research.py`
- `XGBOOST_FULL_RESEARCH_REPORT.md`, this validation document, and the isolated XGBoost run artifacts/report.

Modified:

- `services/api/app/services/model_research.py` — optional read-only benchmark loading and registry.
- `services/api/tests/test_applications.py` — existing admin/ownership regression coverage extended to benchmark data.
- `apps/web/components/model-research-dashboard.tsx` — comparison, ranking, calibration, and SHAP display.
- `apps/web/tests/model-research.spec.ts` — saved-artifact browser coverage and screenshots.
- `PROJECT_PROGRESS.md`, `PROJECT_STATUS_REPORT.md`, `MODEL_RESEARCH_DASHBOARD_REPORT.md`, and `CHANGELOG.md` — milestone tracking and current dashboard/experiment inventory.

No prediction path, Lite artifact, LightGBM artifact, Installment Intelligence implementation, segmentation implementation/artifact, authentication behavior, database schema, or migration is changed by this milestone.

## Reproduction

From `ml/`, run `.venv/Scripts/python.exe -u tools/xgboost_full_research.py` to create a new isolated benchmark run. This trains XGBoost and updates only its own latest pointer. To finish reporting an already saved model, use `.venv/Scripts/python.exe -u tools/xgboost_full_research.py --resume-run 20261004T151458Z`; it verifies preserved inputs before reusing the estimator.
