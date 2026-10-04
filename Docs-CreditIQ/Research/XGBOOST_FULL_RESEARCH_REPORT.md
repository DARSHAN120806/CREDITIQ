# XGBoost FULL_RESEARCH_V1_NO_EXT benchmark

**Completed:** 4 October 2026  
**XGBoost run:** `20261004T151458Z`  
**LightGBM baseline:** `20261004T075100Z`  
**Status:** `mode=RESEARCH_ONLY`, `release_ready=false`

## Finding

XGBoost is slightly worse than the existing LightGBM research baseline on all four paired test metrics. This experiment provides no performance reason to replace the existing LightGBM research candidate. The differences are small point estimates, not evidence of statistical significance. The Lite application model remains unchanged.

| Metric | Existing LightGBM | New XGBoost | XGBoost minus LightGBM | Better direction |
|---|---:|---:|---:|---|
| ROC-AUC | 0.704740208 | 0.704071560 | -0.000668648 | Higher |
| Average Precision | 0.176408925 | 0.175962486 | -0.000446439 | Higher |
| Brier Score | 0.073048583 | 0.073083080 | +0.000034497 | Lower |
| Log Loss | 0.266748575 | 0.266766936 | +0.000018361 | Lower |

The descriptive research ranking is **1. LightGBM, 2. XGBoost**, using Brier ascending and ROC-AUC descending as the tie-break. This display ranking does not select or promote a serving model.

## Exact data and methodology

- Reused the existing `full_research_v1_no_ext_train.parquet`: 278,220 eligible labeled applicants, the same 22 ordered feature inputs, and the same target labels.
- Reused the pinned Lite applicant partitions already used by LightGBM: development 166,932; calibration 41,733; policy 27,822; test 41,733. Partition uniqueness, exhaustiveness, disjointness, and paired test identity/label alignment are checked.
- Kept policy data unused in tuning/calibration selection. No new data eligibility rules or feature definitions were introduced.
- Used the existing XGBoost estimator, fold-fitted preprocessing, and fitting-fold class imbalance weighting. Only XGBoost predictive estimators were trained.
- Matched the LightGBM research search methodology: three outer development folds, three inner tuning folds, five Optuna trials per search, 10,000-row inner tuning subsamples, random seed 42, and final tuning on all development rows.
- Compared sigmoid and isotonic calibration on the outer development assessments, selecting the lowest mean Brier and then highest ROC-AUC. Refit the final model on development and fit the selected calibrator on the separate calibration partition at natural prevalence.
- Reused saved LightGBM test probabilities; the LightGBM estimator was not retrained or executed by this benchmark. Recomputed LightGBM metrics agree with its saved metadata.

**Test-reuse disclosure:** these are the same 41,733 test applicants inspected during earlier research. This is a reused-holdout benchmark, not fresh independent confirmation. Hyperparameters and calibration were fixed without using this run's test metrics. No external or prospective validation is claimed.

The source contract has a known stale top-level `features` array. The benchmark uses the 22 `feature_definitions`, verified against the fitted LightGBM metadata and exact dataset schema, without modifying that contract.

## Calibration results

| Development calibration candidate | ROC-AUC | Average Precision | Brier |
|---|---:|---:|---:|
| **Sigmoid — selected** | 0.689722886 | 0.172984321 | 0.073388398 |
| Isotonic | 0.688338041 | 0.165843652 | 0.073468280 |

Both final benchmark models use sigmoid calibration. The saved calibration JSON and plot show ten quantile reliability bins per model on the common test cohort. The sigmoid calibration component uses logistic regression on model outputs; no standalone Logistic Regression benchmark was trained.

## Paired prediction comparison

The paired CSV and parquet contain one row per test applicant: ID, target, LightGBM probability, XGBoost probability, and XGBoost-minus-LightGBM difference.

- Paired rows: **41,733**.
- Mean LightGBM probability: **0.08344210**.
- Mean XGBoost probability: **0.08325344**.
- Mean absolute probability difference: **0.00980817**, about **0.981 percentage points**.
- Prediction correlation: **0.97131965**.

These describe agreement between the saved predictions; they are not lending-policy or decision-change analyses.

## SHAP importance

Native XGBoost exact Tree SHAP was computed on the same deterministic 1,000-row test sample used by the earlier LightGBM analysis. Values explain **uncalibrated raw margins**. Output dimensions and additivity, including the bias term, were verified. The dashboard serves saved importance values only; it does not calculate SHAP at request time.

| Rank | Transformed feature | Mean absolute SHAP |
|---:|---|---:|
| 1 | payment_principal_ratio | 0.296631 |
| 2 | loan_to_goods_price_ratio | 0.160643 |
| 3 | age_years | 0.145137 |
| 4 | years_employed | 0.144442 |
| 5 | education_level_HIGHER | 0.089424 |
| 6 | employment_type_WORKING | 0.075667 |
| 7 | quoted_monthly_payment | 0.072493 |
| 8 | requested_amount | 0.057631 |
| 9 | credit_bureau_inquiry_history_missing | 0.049739 |
| 10 | credit_bureau_inquiries_12m | 0.045355 |

The complete importance list and top 20 are saved separately. Categorical inputs appear as expanded one-hot columns. Importance magnitude does not give direction, causality, or a contribution to calibrated probability.

## Artifacts and dashboard

All experiment outputs are in `ml/research_output/xgboost_full_research_v1_no_ext/20261004T151458Z/`:

- `xgboost_model.joblib`, `metadata.json`, and `training_metadata.json`.
- `model_comparison.csv` and `model_comparison.json`.
- `calibration_results.json` and `calibration_comparison.png`.
- `shap_feature_importance.csv`, `top_20_features.csv`, and `shap_top_20.png`.
- `paired_test_predictions.parquet` and `paired_test_predictions.csv`.
- `development_model_selection.csv`, `development_selection_folds.csv`, and `development_fold_lineage.json`.
- `preserved_artifact_hashes.json` and the generated run-level `XGBOOST_FULL_RESEARCH_REPORT.md`.

The existing admin-only `/admin/model-research` page includes an XGBoost section, LightGBM comparison, descriptive ranking, calibration curves, SHAP importance, and artifact registry entry. Its API continues to read saved artifacts only. Existing fields remain available; the benchmark is an additive optional response section.

Model reload probability parity passed. All **42 protected files** retained identical SHA-256 hashes, including Lite artifacts, NO_EXT LightGBM outputs, segmentation outputs, and research contracts. See [XGBOOST_FULL_RESEARCH_VALIDATION.md](XGBOOST_FULL_RESEARCH_VALIDATION.md) for tests, screenshots, files changed, and preservation boundaries.

## Recommendation

Keep the existing research LightGBM baseline and the existing application Lite model. Do not claim an XGBoost improvement from this run. Further work should predeclare its evaluation question and acceptance criteria, and use independent temporal/external evidence where available. Feature availability, income/annuity semantics, target horizon, fairness, and deployment suitability remain unresolved research limitations.
