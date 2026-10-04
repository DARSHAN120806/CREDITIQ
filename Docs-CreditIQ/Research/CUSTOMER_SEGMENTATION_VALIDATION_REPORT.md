# Customer Segmentation V1 Validation Report

**Date:** 4 October 2026  
**Status:** `mode=RESEARCH_ONLY`, `release_ready=false`  
**Selected run:** `20261004T132301Z`  
**Source:** `FULL_RESEARCH_V1_NO_EXT`, run `20261004T075100Z`, 278,220 rows, 22 contract features

## Outcome

A separate reproducible K-Means segmentation pipeline and read-only admin dashboard are implemented. The saved train partition was clustered without using `TARGET` or `SK_ID_CURR` as model inputs. `TARGET` was also excluded from cluster selection, profiling, and generated descriptions. The identifier is retained only in the row-level assignment artifact to associate a neutral segment with a source record.

The selected solution has **K=4**. Its silhouette score is **0.0828**, which indicates weak separation and substantial overlap. These clusters are exploratory descriptions of a historical cohort; they are not borrower risk categories, applicant scores, recommendations, or lending decisions.

## Reproducibility and artifacts

The pipeline reads the pinned FULL_RESEARCH_V1_NO_EXT training parquet, checks the source contract and run metadata, and uses numeric median imputation, categorical most-frequent imputation, one-hot encoding, and `StandardScaler`. It evaluates K=2 through K=10. Candidate fitting uses a deterministic sample of 20,000 rows (seed 42); silhouette and Davies-Bouldin use a deterministic 5,000-row metric sample, while inertia is computed on the fitting sample. Solutions with a cluster smaller than 1% are filtered. Of eligible solutions, it selects the maximum silhouette, considers solutions within 0.01, then minimizes Davies-Bouldin and breaks ties toward lower K. Inertia is diagnostic only. The final K-Means model is fit to all 278,220 rows.

Two complete executions produced the same K, metrics, profiles, and assignment file checksum. The first and current assignment parquet SHA-256 is `b885286548a5fb513fdd02301f83df9c72a7559ca2d759ff10acd064b0ced36b`. The current model checksum is `bd779c781d2f82081e6117ee3a0af5f9a2890d84a6f59201d01e5e851f1726f5`. The pipeline reloads the serialized model and verifies that predictions on a fixed sample match before updating `latest.json`.

Artifacts are under `ml/research_output/customer_segmentation/20261004T132301Z/`:

- `segmentation_model.joblib` — fitted preprocessing and K-Means pipeline.
- `cluster_assignments.parquet` — source identifier and neutral cluster ID.
- `cluster_summary.csv` — sizes, percentages, means, and observed-statistic descriptions.
- `cluster_metrics.json` — source checksums, feature list, candidate metrics, selection criteria, profiles, and final model metadata.
- `pca_visualization_data.csv` — deterministic 8,000-row two-component visualization sample without identifiers.
- `SEGMENTATION_REPORT.md` — run-level methodology, findings, and limitations.
- `latest.json` — points to the current run.

### Candidate evaluation

| K | Silhouette | Davies-Bouldin | Inertia (20k fit sample) | Minimum cluster share | Selection eligible |
|---:|---:|---:|---:|---:|:---|
| 2 | 0.0473 | 2.0997 | 971236.36 | 18.00% | Yes |
| 3 | 0.0681 | 3.2656 | 933328.69 | 18.00% | Yes |
| **4** | **0.0828** | 3.0787 | 903255.82 | 9.64% | **Selected** |
| 5 | 0.0780 | 2.1811 | 884367.41 | 0.28% | Filtered |
| 6 | 0.0903 | 2.7850 | 869144.67 | 0.46% | Filtered |
| 7 | 0.0973 | 2.4414 | 846103.54 | 0.28% | Filtered |
| 8 | 0.1136 | 2.4566 | 826978.37 | 0.46% | Filtered |
| 9 | 0.1139 | 2.2951 | 807064.81 | 0.28% | Filtered |
| 10 | 0.1308 | 2.3027 | 790665.55 | 0.46% | Filtered |

The larger K values improve raw silhouette but create clusters below the predeclared 1% minimum. K=4 wins among eligible candidates under the documented rule. The modest score remains a material quality limitation.

### Selected cluster profiles

| Segment | Rows | Share | Mean annual income | Mean requested principal | Mean age | Mean employment years | Description |
|---:|---:|---:|---:|---:|---:|---:|---|
| 1 | 58,616 | 21.07% | 214,645 | 736,151 | 39.3 | 6.5 | Above-cohort income and requested amount; lower average age |
| 2 | 28,166 | 10.12% | 170,083 | 588,742 | 36.2 | 5.4 | Lower average age |
| 3 | 51,884 | 18.65% | 135,647 | 555,490 | 59.9 | 4.6 | Lower income, higher age, lower employment tenure |
| 4 | 139,554 | 50.16% | 162,146 | 617,392 | 42.1 | 6.9 | Near cohort averages across profiled measures |

All requested feature means, including inquiry counts and loan ratios, are in `cluster_summary.csv`. Credit utilization is unavailable from the source contract and displayed as unavailable. Requested principal is not interpreted as total debt.

## Dashboard and access

The dashboard is available at `/admin/customer-segmentation`, with data served by `GET /api/v1/admin/customer-segmentation`. It uses the existing admin RBAC dependency and reads saved artifacts only. The endpoint performs no database writes and does not load the estimator or make predictions. A regular user receives 403.

The UI shows cluster counts and shares, neutral descriptions, feature means, a PCA scatterplot, K selection metrics, methodology, and limitations. The PCA view is a deterministic 2,000-point display subset of the 8,000 saved visualization rows. Screenshots were captured and visually checked:

- Desktop: [customer-segmentation-desktop.png](apps/web/test-results/customer-segmentation-desktop.png)
- Mobile: [customer-segmentation-mobile.png](apps/web/test-results/customer-segmentation-mobile.png)

## Validation

- Pipeline repeatability: two builds; identical assignment SHA-256, selected K, metrics, and profiles.
- Serialization: saved model reloaded and fixed-sample predictions matched.
- Full backend suite: **115 passed**. Includes admin access and response shape, ordinary-user denial, four profiles, nine K candidates, PCA points, and unavailable utilization.
- Frontend Playwright dashboard test: **1 passed**; generated desktop and mobile screenshots.
- TypeScript check: passed.
- Production build: see final status recorded in project progress after build completion.
- Existing Lite and Installment Intelligence paths were not changed. No model was trained or modified; K-Means here is unsupervised customer segmentation.

The backend test run emitted one existing Starlette/httpx deprecation warning. No test failures remain in the checks listed above.

## Limitations and remaining work

- Silhouette 0.0828 is weak; groups overlap and should not be treated as stable customer types.
- The dataset is historical Home Credit data and may not represent CreditIQ users.
- `FULL_RESEARCH_V1_NO_EXT` has no credit utilization feature, and requested amount is not total existing debt.
- Historical bureau inquiry availability for actual CreditIQ applicants is unresolved.
- K-Means geometry is sensitive to scaling, categorical encoding, outliers, and K. PCA omits most feature-space variance and is visualization only.
- Segment numbers are arbitrary and can permute across implementation/library changes; consumers must not attach ordinal meaning to them.
- Outputs are research artifacts and are not approved for lending decisions.

## Change boundary

Only a new segmentation script, saved segmentation artifacts, a read-only admin artifact loader/route, an admin dashboard/navigation entry, UI styles, focused tests, and project documentation were added or changed. Lite model artifacts, FULL_RESEARCH_V1_NO_EXT model artifacts and feature contract, Installment Intelligence, prediction APIs/behavior, authentication, database schema, and migrations remain unchanged. `mode=RESEARCH_ONLY`; `release_ready=false`.
