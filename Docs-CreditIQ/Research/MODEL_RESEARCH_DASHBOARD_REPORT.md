# Model Research Dashboard Report

**Status:** implemented for admin-only research evaluation. `mode=RESEARCH_ONLY`; `release_ready=false`.

## XGBoost extension — 4 October 2026

The page now also displays the saved XGBoost NO_EXT run `20261004T151458Z`: four metrics and deltas against the frozen LightGBM run, descriptive research ranking, calibration selection/curves, native Tree SHAP importance, and a registry entry. LightGBM ranks first and XGBoost second by Brier with ROC-AUC tie-break. No model is promoted. The existing Lite/LightGBM sections remain available, including when the optional XGBoost benchmark is absent. The endpoint reads saved artifacts only and retains existing admin RBAC.

The benchmark was trained separately; no estimator is trained, loaded, or executed by the dashboard. Earlier test-cohort language has been updated to disclose prior inspection. The original implementation record below applies to the earlier two-model dashboard milestone. Current metrics, validation, and desktop/mobile screenshots are documented in [XGBOOST_FULL_RESEARCH_REPORT.md](XGBOOST_FULL_RESEARCH_REPORT.md) and [XGBOOST_FULL_RESEARCH_VALIDATION.md](XGBOOST_FULL_RESEARCH_VALIDATION.md).

## What was delivered

- Admin page: `/admin/model-research`.
- Read-only, admin-protected report endpoint: `GET /api/v1/admin/model-research`.
- Dashboard sections: paired model metrics and deltas, reliability curves and bin values, existing SHAP top-20 chart/ranking, grouped feature contracts, policy-partition feature ablation charts/table, registry metadata, and limitations.
- The endpoint reads pinned metadata/CSV/JSON reports with Python standard-library readers. It does not deserialize or execute model files. The page cannot score applications.
- Existing SHAP values are presented as mean absolute raw-margin contribution; no values are generated or recalculated.

## Model comparison

Both models are LightGBM artifacts evaluated on the same untouched final-test cohort of 41,733 applicants from the 278,220-row eligible cohort.

| Metric | Lite · 17 features | FULL_RESEARCH_V1_NO_EXT · 22 features | Research − Lite | Better direction |
|---|---:|---:|---:|---|
| ROC-AUC | 0.700780 | 0.704740 | +0.003960 | Higher |
| Average Precision | 0.175776 | 0.176409 | +0.000633 | Higher |
| Brier Score | 0.073129 | 0.073049 | −0.000080 | Lower |

Differences are small and descriptive. They do not establish a meaningful, externally validated performance improvement.

## Calibration and reliability

Both saved models use sigmoid calibration. The dashboard plots the 10 saved predicted-probability/observed-rate bins for each model from the shared untouched final-test cohort. Brier scores are included in the overview. The page does not fit calibration curves or recalculate probabilities.

## SHAP and feature contracts

The dashboard loads `shap_feature_importance.csv` and `top_20_features.csv` from the research run and displays the saved top 20. Leading features are `payment_principal_ratio` (0.2804), `loan_to_goods_price_ratio` (0.1396), `years_employed` (0.1293), and `age_years` (0.1278), measured as mean absolute raw-margin SHAP contribution.

The grouped contract view reads feature names from each run's saved metadata. Lite has 17 features; FULL_RESEARCH_V1_NO_EXT has 22. The five additions comprise four credit-bureau inquiry fields and `loan_to_goods_price_ratio`.

## Ablation diagnostics

These existing results use the reserved policy partition and are explicitly labeled diagnostic; they are not final-test comparisons.

| Variant | Features | ROC-AUC | Average Precision | Brier Score |
|---|---:|---:|---:|---:|
| FULL_RESEARCH_V1_NO_EXT | 22 | 0.690999 | 0.173682 | 0.073346 |
| Lite feature subset | 17 | 0.687995 | 0.174290 | 0.073385 |
| Without inquiry features | 18 | 0.688205 | 0.173259 | 0.073400 |
| Without loan-to-goods ratio | 21 | 0.688711 | 0.174635 | 0.073345 |

## Artifact registry and sources

| Model | Run/version | Training date | Calibration | Dataset size | Status |
|---|---|---|---|---:|---|
| Lite | `20261002T140817Z-045430a7` | 2026-10-02 | sigmoid | 278,220 | Current application baseline · research mode |
| FULL_RESEARCH_V1_NO_EXT | `20261004T075100Z` | 2026-10-04 | sigmoid | 278,220 | Research candidate · RESEARCH_ONLY |

Loaded Lite metadata from `ml/real_data_output/artifacts/lite/runs/20261002T140817Z-045430a7/metadata.json` and paired comparison/calibration data from `ml/research_output/full_research_v1_no_ext/20261004T075100Z/metadata.json` and `calibration_results.json`. Loaded research SHAP and ablation data from `shap_feature_importance.csv`, `top_20_features.csv`, and `feature_ablation_summary.csv` in the same run directory. Latest run pointers are validated before files are read.

Lite's nine artifact hashes were checked against its metadata; all matched. The research model file SHA-256 at validation was `8db3846e943dd2f0eb93d8b3d7891f6aa7f10f629a9ccbbe30f03681fa91fc37`.

## Screenshots

- Desktop: [model-research-desktop.png](apps/web/test-results/model-research-desktop.png)
- Mobile: [model-research-mobile.png](apps/web/test-results/model-research-mobile.png)

Both were generated by the Playwright dashboard journey and visually inspected.

## Limitations shown in the dashboard

- Research only; not production approved and not for lending decisions.
- External validation has not been completed; comparison is on one shared Home Credit holdout.
- Real-applicant availability of bureau inquiries remains unresolved.
- TARGET population and outcome horizon have not been independently established.
- SHAP associations are not causal explanations or applicant-level lending reasons.
- Ablation metrics come from a separate policy partition and should not be compared as if they were final-test estimates.

## Verification

- Backend: `tests/test_applications.py` — **16 passed**, including regular-user 403, admin artifact endpoint response, feature counts, metrics, calibration-bin count, SHAP ordering and ablation count. One existing Starlette/httpx TestClient deprecation warning.
- Frontend: `npm run typecheck` passed; `npm test -- --grep "admin model research dashboard"` — **1 passed**; `npm run build` passed.
- No model training/retraining command was run. No Lite or FULL_RESEARCH_V1_NO_EXT artifact, metadata, research report, training pipeline, or contract was modified.
- No migrations or database writes were added. Existing authentication behavior and prediction endpoints were not changed. The only new API is an admin-protected GET endpoint for saved research reports.

No production-readiness claim is made. `release_ready=false` remains in effect.
