# FULL_RESEARCH_V1_NO_EXT research report

**Run:** `20261004T075100Z`  
**Status:** completed controlled research comparison; `mode=RESEARCH_ONLY`, `release_ready=false`.  
**Artifacts:** `ml/research_output/full_research_v1_no_ext/20261004T075100Z/`

## Feature contract and cohort

`FULL_RESEARCH_V1_NO_EXT` is a separate 22-feature contract derived from the existing 28-feature `FULL_RESEARCH_V1`. It removes exactly `EXT_SOURCE_1`, `EXT_SOURCE_2`, `EXT_SOURCE_3`, and their three missingness indicators. The other 22 feature definitions and ordering are retained unchanged. No production feature contract or serving path was edited.

The dataset contains the same 278,220 eligible labeled applicants and the same target labels as the prior research dataset. Training, calibration, policy and final-test applicant IDs reuse the pinned Lite run's saved partitions (166,932 / 41,733 / 27,822 / 41,733). This enables a paired comparison against the existing Lite predictions for the same 41,733 final-test applicants. The Lite artifact was loaded as evaluation evidence only and was not changed or retrained.

The experiment uses the repository's research methodology: development-only nested selection and Optuna tuning, fold-fitted preprocessing, natural-prevalence calibration on the separate calibration split, and one final-test evaluation. LightGBM is the only estimator trained. The selected calibration method was sigmoid. Feature ablations use the reserved policy partition as diagnostics; they do not select or change the final model.

## Paired final-test comparison

| Metric | Existing Lite | FULL_RESEARCH_V1_NO_EXT | Change (NO_EXT − Lite) |
|---|---:|---:|---:|
| ROC-AUC | 0.700780 | 0.704740 | +0.003960 |
| Average Precision | 0.175776 | 0.176409 | +0.000633 |
| Brier Score | 0.073129 | 0.073049 | −0.000080 |
| Log loss | 0.267422 | 0.266749 | −0.000674 |

The NO_EXT model is ahead on these point estimates, but the improvement is marginal and should not be described as a meaningful performance gain. Calibration is reported with ten quantile bins in `calibration_results.json` and visualized in `calibration_comparison.png`. Both probability models show similar calibration across the displayed bins. The held-out test has a 8.346% positive-label rate.

## Feature ablation

All rows below use the policy partition (27,822 applicants), with the same LightGBM hyperparameters and calibration method. They are diagnostic, and should not be compared directly with the final-test headline metrics.

| Variant | Features | ROC-AUC | Average Precision | Brier |
|---|---:|---:|---:|---:|
| FULL_RESEARCH_V1_NO_EXT | 22 | 0.690999 | 0.173682 | 0.073346 |
| Lite feature subset | 17 | 0.687995 | 0.174290 | 0.073385 |
| Without inquiry features | 18 | 0.688205 | 0.173259 | 0.073400 |
| Without loan-to-goods ratio | 21 | 0.688711 | 0.174635 | 0.073345 |

On this partition, the added fields offer a small discrimination improvement in aggregate; removing the inquiry features or loan-to-goods ratio does not establish a robust standalone benefit. This one split is not sufficient evidence to choose a production feature set.

## SHAP and interpretation

`shap_feature_importance.csv` and `top_20_features.csv` contain mean absolute Tree SHAP values for the 1,000-row deterministic test sample; `shap_top_20.png` visualizes the leading values. SHAP values explain the LightGBM model's raw margin before sigmoid calibration. They are global importance summaries, not causal effects or explanations of calibrated risk probability.

The largest reported attributions include `payment_principal_ratio` (0.2804), `loan_to_goods_price_ratio` (0.1396), `years_employed` (0.1293), and `age_years` (0.1278). Categorical fields are shown as one-hot transformed columns. Consult the CSV for the complete ranking.

## Recommendation and limitations

Removing EXT_SOURCE features did not hurt this run; NO_EXT slightly exceeded the existing Lite model on the same holdout. The observed deltas are too small to claim that the expanded feature set meaningfully outperforms Lite. Keep Lite as the existing application model and treat NO_EXT as a research candidate pending repeated validation and a predeclared acceptance criterion.

“No EXT_SOURCE” does not mean “production-ready.” The 22-feature contract still relies on the Kaggle application snapshot, including bureau inquiry fields that require a lawful, accessible source at inference time. Income and annuity periods, TARGET horizon/population, demographic fairness, external validation, temporal stability, and lending-policy suitability remain unverified. This experiment does not authorize lending decisions. No CatBoost, XGBoost, Random Forest, backend, frontend, database, or deployment changes were made.

## Artifact inventory

- `FULL_RESEARCH_V1_NO_EXT.json` — versioned run contract; canonical source contract is `ml/research_contracts/FULL_RESEARCH_V1_NO_EXT.json`.
- `full_research_v1_no_ext_train.parquet` — all eligible labeled rows with exactly the 22 inputs, ID, and target.
- `lightgbm_model.joblib`, `metadata.json` — research estimator, calibrator, feature list, split lineage and run metrics.
- `model_comparison.csv` / `.json`, `paired_test_predictions.parquet` — paired final-test metrics and probabilities.
- `calibration_results.json`, `calibration_comparison.png` — reliability-bin results and plot.
- `feature_ablation_summary.csv` — policy-cohort feature ablations.
- `shap_feature_importance.csv`, `top_20_features.csv`, `shap_top_20.png` — SHAP feature ranking.
- `development_model_selection.csv`, `development_selection_folds.csv` — development-only model/calibration selection.

Re-run from `ml/` with `\.venv\Scripts\python.exe tools/full_research_v1_no_ext.py`. Output goes to a new timestamped research run directory and updates only the research experiment's `latest.json`.
