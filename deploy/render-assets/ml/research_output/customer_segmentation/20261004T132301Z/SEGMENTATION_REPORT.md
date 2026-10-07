# Customer Segmentation Research Report

**Status:** RESEARCH_ONLY · `release_ready=false` · descriptive segmentation, not for lending decisions.

## Source and method

- Source contract: `FULL_RESEARCH_V1_NO_EXT`, run `20261004T075100Z`; source rows: 278,220; applicant-level source SHA-256: `31b6e5f08704568a2923e23b3254f03aba5bc1a8177342d6d27191ca4466711f`.
- Clustering uses the 22 contracted feature fields. `SK_ID_CURR` is retained only in the assignment output; `TARGET` is excluded from preprocessing, K selection, fitting, profiles, and descriptions.
- Numeric missing values use training-source medians; categoricals use most-frequent imputation and one-hot encoding. A fitted `StandardScaler` scales the complete encoded feature matrix.
- Candidate K-Means uses a reproducible random sample of up to 20,000 rows (seed 42), `n_init=5`, and `max_iter=150`. Silhouette and Davies-Bouldin are computed on the same first 5,000 rows from that sample; inertia is measured on the full candidate fitting sample.
- Final model uses K-Means with `n_init=10`, `max_iter=300`, and seed 42, fitted on all 278,220 records after the selected K.

## K selection criteria

Only candidates with at least 1% of metric-sample records in every cluster are eligible. Find the best eligible silhouette score; retain candidates within 0.01 of that maximum, then choose the lowest Davies-Bouldin Index, with smaller K as the final tie-break. Inertia is reported as a compactness diagnostic and is not minimized by itself because it decreases as K grows. Selected K: **4**.

| K | Silhouette | Davies-Bouldin | Inertia | Min cluster share | Eligible |
|---:|---:|---:|---:|---:|:---:|
| 2 | 0.0473 | 2.0997 | 971236.36 | 18.00% | Yes |
| 3 | 0.0681 | 3.2656 | 933328.69 | 18.00% | Yes |
| 4 | 0.0828 | 3.0787 | 903255.82 | 9.64% | Yes |
| 5 | 0.0780 | 2.1811 | 884367.41 | 0.28% | No |
| 6 | 0.0903 | 2.7850 | 869144.67 | 0.46% | No |
| 7 | 0.0973 | 2.4414 | 846103.54 | 0.28% | No |
| 8 | 0.1136 | 2.4566 | 826978.37 | 0.46% | No |
| 9 | 0.1139 | 2.2951 | 807064.81 | 0.28% | No |
| 10 | 0.1308 | 2.3027 | 790665.55 | 0.46% | No |

## Cluster profiles

Mean debt is defined as requested application principal (`requested_amount`); it is not total existing debt. The contract has no credit-card utilization field, so utilization is unavailable and is left blank. Cluster descriptions compare observed means to cohort means and have neutral descriptive names only.

| Segment | Size | Share | Mean income | Mean requested amount | Description |
|---|---:|---:|---:|---:|---|
| Segment 1 | 58,616 | 21.07% | 214,645 | 736,151 | This segment has higher-than-cohort-average income, higher-than-cohort-average requested loan amount, lower average age. |
| Segment 2 | 28,166 | 10.12% | 170,083 | 588,742 | This segment has lower average age. |
| Segment 3 | 51,884 | 18.65% | 135,647 | 555,491 | This segment has lower-than-cohort-average income, higher average age, lower average employment tenure. |
| Segment 4 | 139,554 | 50.16% | 162,146 | 617,392 | This segment is near cohort averages across the profiled measures. |

## Limitations

- These are exploratory groups, not risk classes, customer quality labels, recommendations, or lending decisions.
- The research contract intentionally excludes verified bureau/account history; inquiry fields have unresolved real-applicant availability.
- No utilization measure exists in this contract. Do not reinterpret payment-to-income ratios as credit utilization.
- One-hot encoded categories and standardized numeric values determine Euclidean distance; K-Means assumes roughly spherical groups and is sensitive to outliers and preprocessing choices.
- The selected K has a modest silhouette score (0.0828); segment separation is weak, so boundaries should be treated cautiously.
- PCA is a two-dimensional visualization projection only; apparent separation in the plot does not validate segment quality.
- The historical Home Credit population and TARGET horizon are not independently verified; these clusters may not represent CreditIQ users.
- No prediction model was trained, changed, or invoked. Cluster IDs are arbitrary and can permute across independently rebuilt versions.

## Artifacts

- `segmentation_model.joblib` — fitted preprocessing, scaler, and final K-Means pipeline.
- `cluster_assignments.parquet` — applicant ID and neutral cluster ID; no TARGET or risk label.
- `cluster_summary.csv`, `cluster_metrics.json`, `pca_visualization_data.csv`.
