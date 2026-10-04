# CreditIQ Phase 2 — Real Data Validation Report

Validation date: 2 October 2026.

**Initial validation result: BLOCKED for verified-mode training.** All eight supplied Home Credit CSVs are present and readable, and both application files contain all required Lite columns. At initial inspection, `adapter_manifest.json` was absent and the supplied dictionary did not establish the annual-income/monthly-annuity units required by the approved contract. Full has additional normalized-schema and schedule-evidence blockers. **Subsequent user authorization permits Lite RESEARCH-mode training under the explicit assumptions in section 9; it does not certify the units or production readiness.**

No model training was run in this phase. No verification flags were invented, no source CSVs were modified, and synthetic results were not substituted for real-data results.

## 1. Location and inspection scope

Actual dataset directory:

`C:\Users\darsh\Downloads\creditiq_ml_phase1\ml\data\raw\DATASET_CREDITIQ`

The files are nested one level below the configured default `ml/data/raw`. The loader does not search recursively. Use `--raw-dir data/raw/DATASET_CREDITIQ` from `ml`; moving the files is unnecessary.

Inspected the current v1.1.0 contract, feature adapter and manifest validator. Read the headers of all eight CSVs, streamed all rows of their selected adapter columns, and ran the shared application transformation to determine structural Lite eligibility. Checked application customer uniqueness, train/test identity overlap, targets, required-field missingness, observed categories, and selected relative-date ranges. Read the supplied column dictionary using CP1252 after UTF-8 decoding failed.

Global history-table duplicate-key reconciliation, all relational foreign-key checks, source availability reconstruction, contractual schedule reconciliation and model evaluation were **not** completed. The missing Full schema/evidence prevents declaring Full validity. Streaming selected columns does not certify every unused CSV column.

Machine-readable evidence: `ml/reports/data_validation/validation_snapshot.json`.

## 2. File inventory

| File | Rows read | Header columns | Presence/readability | Current adapter schema |
|---|---:|---:|---|---|
| application_train.csv | 307,511 | 122 | PASS | All required Lite fields present |
| application_test.csv | 48,744 | 121 | PASS | All required Lite fields present; no TARGET column |
| bureau.csv | 1,716,428 | 17 | PASS | Missing DAYS_AVAILABLE |
| bureau_balance.csv | 27,299,925 | 3 | PASS | Missing DAYS_AVAILABLE |
| previous_application.csv | 1,670,214 | 37 | PASS | Missing DAYS_AVAILABLE |
| installments_payments.csv | 13,605,401 | 8 | PASS | Missing DAYS_AVAILABLE and PAYMENT_ID |
| POS_CASH_balance.csv | 10,001,358 | 8 | PASS | Missing DAYS_AVAILABLE |
| credit_card_balance.csv | 3,840,312 | 23 | PASS | Missing DAYS_AVAILABLE |

Also present: `HomeCredit_columns_description.csv` (CP1252 encoding).

Missing: `adapter_manifest.json` and the supplementary `installment_schedule.csv` required for Full. No duplicate header names were found.

The missing Full fields are requirements of the remediated normalized adapter, not evidence that the original Home Credit download is corrupt. The original files must not be modified by assigning arbitrary dates or payment IDs just to make the validator pass.

## 3. Required column verification

### Application files — Lite

All the following required columns are present in both application CSVs:

- SK_ID_CURR
- NAME_CONTRACT_TYPE
- DAYS_BIRTH
- DAYS_EMPLOYED
- AMT_INCOME_TOTAL
- AMT_CREDIT
- AMT_ANNUITY
- CNT_FAM_MEMBERS
- CNT_CHILDREN
- NAME_INCOME_TYPE
- NAME_EDUCATION_TYPE

`TARGET` is present in training and absent from competition test, as expected. Optional `OCCUPATION_TYPE` and `NAME_HOUSING_TYPE` are present in both files. These source columns produce the 17 semantic Lite features; the CSV is not expected to contain precomputed canonical ratios.

### History files — Full

| Source | Existing required columns verified present | Missing normalized fields |
|---|---|---|
| bureau | SK_ID_CURR, SK_ID_BUREAU, DAYS_CREDIT, CREDIT_ACTIVE, CREDIT_DAY_OVERDUE, AMT_CREDIT_SUM, AMT_CREDIT_SUM_DEBT, AMT_CREDIT_SUM_OVERDUE | DAYS_AVAILABLE |
| bureau_balance | SK_ID_BUREAU, MONTHS_BALANCE, STATUS | DAYS_AVAILABLE |
| previous_application | SK_ID_CURR, SK_ID_PREV, DAYS_DECISION, NAME_CONTRACT_STATUS | DAYS_AVAILABLE |
| installments_payments | SK_ID_CURR, SK_ID_PREV, NUM_INSTALMENT_NUMBER, NUM_INSTALMENT_VERSION, DAYS_ENTRY_PAYMENT, AMT_PAYMENT; repeated DAYS_INSTALMENT and AMT_INSTALMENT are also present | DAYS_AVAILABLE, PAYMENT_ID |
| POS_CASH_balance | SK_ID_CURR, SK_ID_PREV, MONTHS_BALANCE, SK_DPD, NAME_CONTRACT_STATUS | DAYS_AVAILABLE |
| credit_card_balance | SK_ID_CURR, SK_ID_PREV, MONTHS_BALANCE, SK_DPD, NAME_CONTRACT_STATUS, AMT_BALANCE, AMT_CREDIT_LIMIT_ACTUAL | DAYS_AVAILABLE |

Full additionally requires an effective schedule with SK_ID_CURR, SK_ID_PREV, NUM_INSTALMENT_NUMBER, NUM_INSTALMENT_VERSION, DAYS_INSTALMENT, AMT_INSTALMENT and DAYS_AVAILABLE. No such schedule was supplied. The existing payment table is not assumed to enumerate every never-paid contractual obligation.

## 4. Application quality and Lite eligibility

| Check | Training | Competition test |
|---|---:|---:|
| Input rows | 307,511 | 48,744 |
| Duplicate customer IDs | 0 | 0 |
| Null customer IDs | 0 | 0 |
| Cash-loan rows | 278,232 | 48,305 |
| Revolving-loan exclusions | 29,279 | 439 |
| Cash-loan rows excluded for missing annuity | 12 | 24 |
| Structurally eligible Lite rows | **278,220** | **48,281** |

**Train/test customer overlap: 0.**

Training TARGET has no missing values and contains only 0 and 1. Full training-file counts are 282,686 negatives and 24,825 positives. Among the structurally eligible Lite rows, counts are **254,999 negatives and 23,221 positives**, giving **8.3463% TARGET=1 prevalence**. This is a descriptive dataset statistic, not a model metric or approval threshold.

Observed nonmissing employment, education, occupation and housing categories all have entries in the canonical mapping. This verifies mapping coverage, not whether a future user will interpret each label consistently. The cash/revolving distinction is documented and implemented by the cohort filter.

Additional missingness:

- OCCUPATION_TYPE: 96,391 missing training values and 15,605 missing test values. This field is optional and uses the explicit MISSING category.
- CNT_FAM_MEMBERS: two missing training values, none in test. No additional eligible cash-loan rows were excluded for this field; exclusion reasons are reported in the adapter's validation order, not as independent marginal counts.
- AMT_ANNUITY: 12 missing training values and 24 missing test values, matching the cash-loan exclusions above.

The shared adapter accepted the remaining rows' numerical and household constraints. There are enough positives and negatives to construct the planned partitions once the evidence gates pass. No model, calibrator or threshold was fitted during these checks.

## 5. History quality observations

- Bureau AMT_CREDIT_SUM is missing on 13 rows; AMT_CREDIT_SUM_DEBT is missing on 257,669 rows. Missing debt cannot be treated as confirmed zero. The adapter preserves unknown totals.
- Installment DAYS_ENTRY_PAYMENT and AMT_PAYMENT each have 2,905 missing values. The current reconciler requires known payment events; these require explicit source interpretation/reconciliation, not invented dates or amounts. Equal counts alone do not establish they are the same rows.
- No positive DAYS_CREDIT, DAYS_DECISION, DAYS_ENTRY_PAYMENT, DAYS_INSTALMENT or MONTHS_BALANCE values were found in the relevant scanned fields. This does **not** prove information was available by the decision cutoff: event date and availability date are different concepts.
- The dictionary states that installment-calendar version 0 is associated with credit cards and that version changes indicate calendar changes. This reinforces the need to resolve schedule semantics before Full reconciliation; simply choosing the largest version is not justified.
- Duplicate-payment identity, schedule completeness and global history ownership/cardinality remain unverified. They were not inferred from apparent dataset size or familiar filenames.

## 6. Manifest and evidence gates

No `adapter_manifest.json` exists in the actual dataset directory. The example manifest at `ml/adapter_manifest.example.json` is a template, not dataset evidence, and was not copied or marked verified.

The existing validator was invoked with the actual dataset path for both variants. Both returned:

`ContractError: Missing adapter_manifest.json: verify source semantics before training`

| Gate | Evidence/status | Impact |
|---|---|---|
| Correct raw path | Nested directory found; explicit --raw-dir resolves it | Operational instruction, not an intrinsic data defect |
| Lite required columns | PASS | No application schema blocker |
| cash_product_verified | Dictionary and observed values support cash/revolving distinction; declaration absent | Record evidence in manifest |
| category_mapping_verified | All observed nonmissing values mapped; declaration absent | Record mapping review and evidence |
| annuity_monthly_verified | NOT VERIFIED | Blocks Lite and Full under approved design |
| Annual income units | NOT VERIFIED by supplied dictionary | Required for correct payment-to-income derivation |
| Currency/domain and evidence | No manifest declaration | Declare research units explicitly; do not claim INR or another currency without evidence |
| Real-data provenance | Supplied by user as real Home Credit data; no dataset manifest | Record provenance; never use synthetic fixture evidence |
| Full source states/coverage | No manifest entries | Full blocked |
| availability_verified | No availability columns/evidence | Full blocked |
| payment_identity_verified | PAYMENT_ID absent | Full blocked |
| schedule_complete | Supplementary complete schedule absent | Full blocked |
| schedule_versions_resolved | No effective-schedule reconciliation evidence | Full blocked |

### Why units were not automatically certified

The supplied application dictionary describes AMT_INCOME_TOTAL as **“Income of the client”** and AMT_ANNUITY as **“Loan annuity.”** These descriptions do not explicitly establish annual income or monthly payment frequency. The feature calculation divides income by 12, so a mistaken frequency assumption would change the payment-to-income feature by a material factor.

The target dictionary describes payment difficulty using unspecified **X days** and **Y initial installments**. It does not establish a 12-month or lifetime probability horizon. No such claim is made by this validation.

The current manifest validator mechanically checks affirmative flags and nonempty evidence; it does not independently establish that an evidence statement is true. Therefore changing flags to true without supporting documentation would not resolve this validation.

## 7. Training decision and requested model outputs

**Lite training was not started because validation did not pass.** The Full-specific blockers would not, by themselves, prevent Lite research training; Lite is blocked here by its own missing manifest and unresolved monetary-unit evidence.

| Requested output | Status |
|---|---|
| Real-data model comparison table | Not generated |
| ROC-AUC | Not measured |
| Average Precision | Not measured |
| Brier score | Not measured |
| Calibration results | Not measured |
| Predicted risk-band distribution | Not generated |
| LITE_MODEL_REPORT.md | Not generated: conditional training phase not reached |

Existing synthetic artifacts remain synthetic and are not evidence for any of these outputs. No new model artifacts were produced during this validation.

## 8. Release blockers and next step

**Immediate Lite blockers:** create an evidence-backed dataset manifest and resolve annual-income/monthly-annuity semantics and monetary domain. The schema and structural cohort checks already pass. Do not make Full history reconstruction a prerequisite for this independent Lite task.

**Additional Full blockers:** normalized availability fields, reliable payment-event identities, complete effective schedule and source-coverage/version evidence; reconcile unknown payment dates/amounts and perform global relationship checks afterward.

**Later production blockers:** independently evaluated real-data discrimination/calibration and cohort performance, verified target/population interpretation, and an approved live decision policy. Structural validation or successful training alone does not establish production readiness.

Recommended next action: obtain authoritative unit/provenance documentation and complete `ml/data/raw/DATASET_CREDITIQ/adapter_manifest.json` with evidence references. If documentation cannot establish the approved units, explicitly revisit the feature contract rather than bypassing the gate. Revalidate before fitting.

After the Lite gates genuinely pass, run from the project ML folder:

```powershell
Set-Location 'C:\Users\darsh\Downloads\creditiq_ml_phase1\ml'
.\.venv\Scripts\python.exe -m creditiq_ml.cli train --feature-set lite --raw-dir data/raw/DATASET_CREDITIQ --output-dir real_data_output --models logistic_regression decision_tree random_forest xgboost lightgbm --trials 25 --no-cache
```

This isolates real-data outputs from smoke outputs. The command is a future continuation step; it was not executed in this phase. Once training completes, summarize its immutable run's comparison, final-test metrics, calibration curve and band outcomes in LITE_MODEL_REPORT.md.

## 9. Research authorization addendum — 2 October 2026

After the initial validation, the user explicitly authorized RESEARCH mode with these assumptions:

1. Source is the standard Kaggle Home Credit Default Risk dataset, as asserted by the user.
2. AMT_INCOME_TOTAL is treated as annual income.
3. AMT_ANNUITY is treated as monthly loan payment for feature engineering.
4. Currency is unspecified research currency, represented by XXX.
5. The assumptions must be recorded in metadata and reports; release_ready remains false and production readiness is not claimed.

Created `ml/data/raw/DATASET_CREDITIQ/adapter_manifest.json` containing those declarations. The monthly-annuity verification flag deliberately remains false. The validator now accepts this narrowly scoped, explicit Lite research authorization while keeping the Full gates intact. Category mapping and cash-product evidence come from the checks above.

The initial “not run” observations in sections 1–8 describe the original validation checkpoint. The authorized subsequent run compares all five model families using five Optuna trials for each boosted family per search and a maximum of 10,000 development rows per tuning search. No overall cohort subsampling is requested; final model fitting uses the entire development cohort. Outputs are isolated under `ml/real_data_output`. Consult LITE_MODEL_REPORT.md for the completed run's actual results when available.


## 10. Completed real-data research run

Run `20261002T140817Z-045430a7` completed successfully with 278,220 eligible labeled applications and all five model families compared. Champion: lightgbm / sigmoid. Final-test ROC-AUC: 0.700780; Average Precision: 0.175776; Brier: 0.073129. The full suite passed 45 tests. See [LITE_MODEL_REPORT.md](LITE_MODEL_REPORT.md) for protocol, results and artifact links. Research assumptions remain assumptions; `release_ready=false`. Full-source and production release blockers above remain unresolved.
