# CreditIQ Lite real-data research report

Run: `20261002T140817Z-045430a7`. Completed: 2026-10-02T14:23:19.954512+00:00. Mode: **RESEARCH**. `release_ready=false`; `synthetic=false`. No production readiness is claimed.

## Outcome

All five model families completed nested development comparison. The frozen champion is **lightgbm with sigmoid calibration**. A real-data model, metadata, split identities, comparison table, calibration plots and final-test predictions were generated. The complete test suite passed: **45 tests, 4 upstream SHAP warnings**. Artifact hashes, disjoint split identities, current source-code hashes and loaded-model predictions were independently checked after training.

## Explicit assumptions

- Dataset is the standard Kaggle Home Credit Default Risk dataset, as asserted by the user; independent download provenance is not established.
- `AMT_INCOME_TOTAL` is treated as **annual income**.
- `AMT_ANNUITY` is treated as **monthly loan payment** for feature engineering. Its verification flag remains false; this is an authorized assumption.
- Monetary values use **unspecified research currency**, represented by `XXX`; no currency conversion is claimed.
- Predictions estimate the dataset's `TARGET=1` payment-difficulty outcome. A fixed default horizon has not been established.
- These assumptions are stored in the adapter manifest and both model and JSON metadata. They do not authorize live credit decisions.

## Data and evaluation protocol

All eight requested CSVs were found under `ml/data/raw/DATASET_CREDITIQ`. See [data validation report](DATA_VALIDATION_REPORT.md) for schemas and Full-model blockers. Lite uses application data only.

Of 307,511 labeled applications, 278,220 are eligible: 254,999 TARGET=0 and 23,221 TARGET=1 (8.3463%). The exclusions are 29,279 revolving-loan records and 12 records missing annuity. The separate Kaggle application_test.csv has no target and is not the reported held-out test cohort.

The 17-feature Lite contract and shared transformations are retained. The random, stratified customer partitions are:

| Partition | Rows |
| --- | --- |
| calibration | 41,733 |
| development | 166,932 |
| policy | 27,822 |
| test | 41,733 |

Three development outer folds assess model/calibration combinations; each fold reserves separate calibration rows and runs three-fold inner tuning. Model selection minimizes mean outer Brier, then maximizes ROC-AUC. Only the selected champion is evaluated on final test. Comparison rows below are development estimates, not a test leaderboard. The final calibrator uses only the dedicated calibration split; policy diagnostics use only the policy split.

Search budget: 10,000 rows maximum per inner tuning search; five Optuna trials per search for XGBoost and LightGBM. Logistic regression, decision tree and random forest use their existing grids. No overall data subsample is used; the final estimator fits all 166,932 development rows. This bounded search is not exhaustive. Seed: 42. Class-weighted fitting is followed by unweighted calibration at natural prevalence.

## Model comparison — mean outer-development metrics

| Model | Calibration | ROC-AUC | Average Precision | Brier |
| --- | --- | --- | --- | --- |
| lightgbm | sigmoid | 0.685518 | 0.170222 | 0.073527 |
| xgboost | sigmoid | 0.685300 | 0.169950 | 0.073533 |
| lightgbm | isotonic | 0.684076 | 0.163223 | 0.073646 |
| xgboost | isotonic | 0.684144 | 0.163673 | 0.073717 |
| random_forest | sigmoid | 0.658698 | 0.151276 | 0.074406 |
| random_forest | isotonic | 0.656899 | 0.144846 | 0.074470 |
| decision_tree | isotonic | 0.642220 | 0.130444 | 0.074897 |
| logistic_regression | sigmoid | 0.643452 | 0.138115 | 0.074899 |
| logistic_regression | isotonic | 0.642381 | 0.132904 | 0.074937 |
| decision_tree | sigmoid | 0.641664 | 0.132428 | 0.074944 |

[Comparison CSV](ml/real_data_output/reports/training/lite/20261002T140817Z-045430a7/model_comparison.csv); [individual fold results](ml/real_data_output/reports/training/lite/20261002T140817Z-045430a7/development_folds.csv). Development selection can be optimistic; the untouched final test provides the champion assessment.

## Frozen champion — final test

| Metric | Estimate | Bootstrap 95% interval |
| --- | --- | --- |
| ROC_AUC | 0.700780 | 0.690483 – 0.708383 |
| AveragePrecision | 0.175776 | 0.167546 – 0.185618 |
| Brier | 0.073129 | 0.071265 – 0.075201 |

Intervals use 200 applicant bootstrap resamples of fixed predictions; they do not include retraining or population-shift uncertainty. Average Precision is the reported precision-recall summary, not trapezoidal PR-AUC.

Test prevalence / no-skill Average Precision: **0.083459**. Constant development-prevalence predictor Brier: **0.076494**. Always-zero accuracy: 91.65%; accuracy alone is not a useful success criterion for this imbalance.

The champion shows moderate discrimination. Average Precision is about 2.11 times prevalence, and Brier is approximately 4.40% lower than the constant-risk baseline. These improvements establish useful research signal, without demonstrating acceptable lending performance or superiority over models outside this bounded comparison.

[All test metrics](ml/real_data_output/reports/training/lite/20261002T140817Z-045430a7/test_metrics.json); [ROC plot](ml/real_data_output/reports/training/lite/20261002T140817Z-045430a7/roc_curves.png); [precision-recall plot](ml/real_data_output/reports/training/lite/20261002T140817Z-045430a7/pr_curves.png). Threshold metrics in the JSON use 0.15 solely as sandbox diagnostics.

## Calibration

- Raw classifier Brier: 0.209786; calibrated Brier: 0.073129.
- Raw log loss: 0.606970; calibrated log loss: 0.267422.
- Mean calibrated prediction: 8.35%; observed TARGET=1: 8.35%.
- Quantile-bin weighted absolute calibration gap: 0.002986 (10 nonempty bins). This is descriptive, depends on binning, and is not a release gate.

![Calibration diagnostics](ml/real_data_output/reports/training/lite/20261002T140817Z-045430a7/calibration_diagnostics.png)

[Calibration-bin table](ml/real_data_output/reports/training/lite/20261002T140817Z-045430a7/calibration_bins.csv); [original calibrated reliability plot](ml/real_data_output/reports/training/lite/20261002T140817Z-045430a7/calibration.png). Class-weighted raw scores need not estimate natural-prevalence probabilities. No recalibration or threshold changes were made using these final-test diagnostics.

## Risk-band distribution — final test

Risk score = 100 × calibrated probability. Low: p < 0.05; Medium: 0.05 ≤ p < 0.15; High: p ≥ 0.15. These are research bands, not approved lending thresholds.

| Band | Applicants | Share | Mean probability | Observed TARGET=1 |
| --- | --- | --- | --- | --- |
| Low | 13,405 | 32.12% | 3.25% | 3.13% |
| Medium | 22,970 | 55.04% | 8.56% | 8.57% |
| High | 5,358 | 12.84% | 20.20% | 20.46% |

![Risk-band distribution](ml/real_data_output/reports/training/lite/20261002T140817Z-045430a7/risk_band_distribution.png)

All actual decisions remain **MANUAL_REVIEW**. Sandbox approval/rejection candidate labels must not be presented as final approvals or rejections. [Policy diagnostics](ml/real_data_output/reports/training/lite/20261002T140817Z-045430a7/policy_validation.json) describe candidate thresholds on the independent policy partition.

## Artifacts and verification

- [Trained model](ml/real_data_output/artifacts/lite/runs/20261002T140817Z-045430a7/best_model.joblib)
- [Metadata, assumptions, parameters, package versions and hashes](ml/real_data_output/artifacts/lite/runs/20261002T140817Z-045430a7/metadata.json)
- [Post-training verification](ml/real_data_output/reports/training/lite/20261002T140817Z-045430a7/research_validation.json)
- [Risk-band CSV](ml/real_data_output/reports/training/lite/20261002T140817Z-045430a7/risk_band_distribution.csv)
- [Training log](ml/real_data_output/training.log)

Training emitted pandas fragmentation performance warnings while loading the source tables; the run completed. Tests emitted three SHAP plotting deprecation warnings and one LightGBM SHAP output-format warning. These warnings did not fail validation. Real-data SHAP explanations and Full segmentation were not generated in this Lite-training task.

## Limitations and release blockers

Successful research training does not establish production suitability. Source provenance, annual/monthly unit assumptions, currency and target horizon remain unverified. Random splits do not measure future-period performance. External/temporal validation, subgroup calibration and performance, monitoring criteria and independently approved lending policy remain open. The limited tuning budget may miss stronger settings; these final-test results must not be repeatedly reused for model selection.

Full training remains blocked by absent availability fields, payment identities, complete unpaid-installment schedules and source-completeness evidence. Lite training does not resolve those issues. `release_ready=false` is retained in the adapter, model and metadata. No backend, frontend, database or deployment files were generated.

Recommended next step: review these research results and run prespecified subgroup and out-of-time validation if appropriate data become available, while resolving source semantics and Full-history evidence. Define acceptance criteria and policy approval independently before any production release.

## Reproduce the training run

From the project root in PowerShell:

```powershell
Set-Location 'C:\Users\darsh\Downloads\creditiq_ml_phase1\ml'
.\.venv\Scripts\python.exe -u -m creditiq_ml.cli train --feature-set lite --raw-dir data/raw/DATASET_CREDITIQ --output-dir real_data_output --models logistic_regression decision_tree random_forest xgboost lightgbm --trials 5 --tune-rows 10000 --no-cache
```

This creates a new versioned run. The present report identifies the run above; repeat runs should not become a way of tuning against this already-inspected test set.
