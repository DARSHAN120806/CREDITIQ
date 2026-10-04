# FULL_RESEARCH_V1 readiness report

**Status: research dataset built and suitable for a controlled research training experiment. No model training was run.** This contract is not production ready and is not connected to the pinned Lite model. Keep `mode=RESEARCH_ONLY` and `release_ready=false`.

The separate contract is [FULL_RESEARCH_V1.json](ml/research_contracts/FULL_RESEARCH_V1.json). The builder is [full_research_v1.py](ml/tools/full_research_v1.py). Final reproducible build: `ml/research_output/full_research_v1/20261004-delivery/`.

## Dataset and coverage

- **28 features**: the existing 17 application Lite features plus 11 application-record features: three external source scores, three score-missingness indicators, three nonoverlapping bureau-inquiry windows, one all-inquiry-history-missing indicator, and loan-to-goods-price ratio.
- **278,220 eligible rows** from 307,511 `application_train.csv` rows. The unchanged adapter excluded 29,291 rows: 29,279 unsupported revolving applications and 12 cash applications missing annuity. The competition test set is excluded.
- Labels: 254,999 TARGET=0 and 23,221 TARGET=1 (**8.35% positive**). The dataset describes TARGET=1 as payment difficulties; its exact outcome horizon and deployment population have not been independently established.
- **100% of eligible applicants have a row** for each contract feature, with missing values retained where the source value is unknown. Complete-case coverage across the 28 features is **31.87% (88,662 rows)**. This is not the expected row loss: fold-fitted imputation can retain all rows, if it passes validation.
- `EXT_SOURCE_1` is missing in **56.79%** of the cohort (43.21% non-null coverage); `EXT_SOURCE_2` is missing in 0.22% (99.78% coverage); `EXT_SOURCE_3` is missing in 19.65% (80.35% coverage). Employment tenure and its derived age ratio are each missing in 18.69% (81.31% coverage). Each selected bureau-inquiry window is missing in 13.38% (86.62% coverage). No imputation was performed. `occupation` is represented by the existing MISSING category for 31.92% of source values (feature-matrix missingness 0%); `housing_status` source missingness is 0%. The inventory reports both transformed-feature missingness and raw-source missingness.
- The three selected inquiry buckets have consistent missingness across the cohort and match disjoint source intervals. Loan-to-goods-price ratio ranges from 1.0 to 1.66; inspect its upper tail in model diagnostics.

All **71 candidate feature rows** include source, definition, missingness, coverage, data-quality notes and KEEP/DROP in [feature_inventory.csv](ml/research_output/full_research_v1/20261004-delivery/feature_inventory.csv). Per-KEEP reports: [missingness](ml/research_output/full_research_v1/20261004-delivery/missingness_report.csv), [coverage](ml/research_output/full_research_v1/20261004-delivery/coverage_report.csv), [distributions](ml/research_output/full_research_v1/20261004-delivery/feature_distributions.json). Dataset: [Parquet](ml/research_output/full_research_v1/20261004-delivery/full_research_v1_train.parquet). Reproduction metadata and input/output hashes: [build_manifest.json](ml/research_output/full_research_v1/20261004-delivery/build_manifest.json).

For excluded features, missingness is reported as N/A because their aggregates were intentionally not calculated. Source-row coverage is supplied as a proxy only; it must not be mistaken for feature coverage. Their individual definitions and exclusion reasons are in [excluded_history_features.csv](ml/research_output/full_research_v1/20261004-delivery/excluded_history_features.csv).

## Selection by priority group

| Group | Decision | Reason |
|---|---|---|
| Repayment behavior | Drop all 9 installment candidates | No effective schedule (including never-paid obligations), payment identity or historical availability evidence. Treating payment rows as installments could count split payments as separate obligations. |
| Bureau delinquency | Drop all 14 bureau and bureau-balance features | No `DAYS_AVAILABLE`; 3,120,184 bureau-balance rows (11.43%) cannot map to supplied bureau accounts; debt null and negative-value semantics need review. |
| POS delinquency | Drop all 6 features | Month offset does not prove the snapshot was available at the loan decision time. |
| Card utilization | Drop all 8 features | No snapshot-availability evidence; negative balance meaning needs review. |
| Debt exposure | Keep loan-to-goods-price ratio; drop bureau totals | Ratio uses the contemporaneous application. Bureau exposure has unresolved mapping and timing. |
| Previous borrowing | Keep 3 inquiry windows from the application record; drop 6 linked prior-application aggregates | The embedded inquiry counts are present on the application snapshot. Historical decisions do not prove what the current lender knew at decision time. |

No missing timestamps, payment IDs, schedules, borrower mappings or verification flags were invented. Source quality issues also include `AMT_CREDIT_SUM_DEBT` missing in 15.01% of bureau rows, 2,905 installment rows missing payment date and amount, 8,418 negative bureau debt values and 2,345 negative card balances. These may be source conventions rather than errors; no automatic correction was applied. See the [prior raw-source audit](ml/full_dataset_output/20261004-readiness-v1/FULL_FEATURE_REPORT.md).

## Assumptions, limitations and leakage review

- The supplied data is the standard Kaggle Home Credit dataset, as asserted by the user.
- `AMT_INCOME_TOTAL` is treated as annual income and `AMT_ANNUITY` as monthly payment under the authorized research assumptions. The currency is unspecified and monetary periods are not independently verified.
- Only the application record is used for predictors. The application snapshot is assumed to represent the prediction-time record. No secondary history enters, avoiding its unresolved as-of availability. Source extraction timing still requires domain validation.
- `EXT_SOURCE_*` values are included as normalized fields already recorded on the application. Their providers and meaning are unknown, and CreditIQ's current user form cannot supply them. Their missingness indicators may encode provider access, not borrower behavior.
- The inherited 17-feature Lite contract includes age, education, occupation, household and housing attributes. Review fairness and proxy effects by subgroup; add ablations before selecting the model.
- TARGET's prediction horizon and population are uncertain. Validate target semantics before interpreting a model score. There are no TARGET-derived predictors in this dataset.
- All raw missing values are preserved. Fit numeric imputation, category handling, scaling, clipping and feature selection inside development folds only.
- No raw external source was joined to CreditIQ user identities; no serving or UI input contract was changed.

## Training recommendation

**Suitable for research training only.** All 28 features are reproducibly generated, IDs are unique, labels are present, and the cohort contains both classes. `release_ready=false`; it is not suitable for production lending decisions until target semantics, source units, inference availability and fairness are validated.

Benchmark LightGBM first, then XGBoost, CatBoost and Random Forest. LightGBM/XGBoost/Random Forest are already in the ML dependency set; CatBoost is not, so use an isolated environment if it is added. Existing Lite metrics are not FULL_RESEARCH_V1 results and must not be presented as such.

Recommended plan: freeze this contract and hashes; confirm target horizon/population and input availability; use deterministic, disjoint borrower ID splits (60% development, 15% calibration, 10% policy, 15% final test); tune only in development cross-validation; fit every preprocessing step inside folds; compare ROC-AUC, Average Precision, Brier score, calibration, subgroup performance and feature-group ablations; set any thresholds on the policy partition; evaluate once on the untouched test. Keep Lite as the serving model until the research result is separately validated and reviewed.

## Preservation and rerun

The builder and contract live under separate `ml/tools` and `ml/research_contracts` paths. Existing Full/Lite contracts, Lite model/artifacts, Installment Intelligence, APIs, schema and raw data were not modified. Model training was not run. `build_manifest.json` fingerprints the seven CSVs, adapter assumptions, dataset, contract, builder, reused feature-pipeline files and runtime.

From `ml`, build to a fresh directory:

```powershell
.\.venv\Scripts\python.exe tools/full_research_v1.py --raw-dir data/raw/DATASET_CREDITIQ --output-dir research_output/full_research_v1/next-run
```

