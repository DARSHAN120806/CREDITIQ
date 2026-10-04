# Full feature dataset — readiness assessment

4 October 2026. **Builder and audit implemented; real Full dataset BLOCKED.**
No model was trained. Lite source, pipeline, artifacts and latest pointer are unchanged.
Keep `mode=RESEARCH_ONLY`, `release_ready=false`, `training_ready=false` for this build.

## Deliverables

Build directory: `ml/full_dataset_output/20261004-readiness-v1`.

| Deliverable | Result |
|---|---|
| Complete 60-feature Full dataset | **Not generated**: cannot pass the existing contract with supplied source evidence |
| Diagnostic application dataset | [application_features_ONLY_NOT_FULL.parquet](ml/full_dataset_output/20261004-readiness-v1/application_features_ONLY_NOT_FULL.parquet): 278,220 rows, 17 features plus customer ID, TARGET and IS_TRAIN |
| Feature availability, missingness and quantiles | [feature_quality.csv](ml/full_dataset_output/20261004-readiness-v1/feature_quality.csv): all 60 contract entries; 17 generated, 43 explicitly blocked |
| Feature distributions | [feature_distributions.json](ml/full_dataset_output/20261004-readiness-v1/feature_distributions.json): histograms and categories for generated features; no fabricated history distributions |
| Coverage | [source_coverage.csv](ml/full_dataset_output/20261004-readiness-v1/source_coverage.csv): six history sources, eligible-applicant coverage and row-count distributions |
| Source data quality | [source_column_quality.csv](ml/full_dataset_output/20261004-readiness-v1/source_column_quality.csv), [source_categories.json](ml/full_dataset_output/20261004-readiness-v1/source_categories.json) |
| Reproducibility and blockers | [build_manifest.json](ml/full_dataset_output/20261004-readiness-v1/build_manifest.json): input/code/dataset SHA-256, runtime versions, unchanged assumptions, all gates |
| Generated readiness report | [FULL_FEATURE_REPORT.md](ml/full_dataset_output/20261004-readiness-v1/FULL_FEATURE_REPORT.md) |
| Reproducible pipeline | [full_dataset.py](ml/tools/full_dataset.py) |

The partial dataset is deliberately not named `full_features.parquet`. It cannot be used
as evidence that Full is complete. No missing history was replaced with zero or with
synthetic values. No competition-test applicants are in the output cohort.

## Application cohort and feature quality

- Source training applications: **307,511**.
- Eligible cash-loan applications: **278,220**.
- Excluded by the unchanged adapter: **29,291** (29,279 unsupported-product rows and 12 missing-annuity rows).
- TARGET counts: 254,999 zero and 23,221 one; no estimator was fitted.
- Generated features: **17/60 (28.33%)**. History features unavailable: **43/60 (71.67%)**.
- Employment tenure and employed-age ratio each have **18.6931% missingness**; the other generated features have no null values.
- Occupation has **88,800 explicit MISSING-category values**. A non-null categorical sentinel is not complete underlying information; see category distributions.
- Blocked features show 0% generated coverage and 100% unavailable values in the quality report. This is a contract blockage, not a measurement of natural null frequency in a completed Full dataset.
- Numeric distributions include minimum, mean, maximum, percentiles 1/25/50/75/99 and histograms. No imputation, clipping or fitted preprocessing was added.

## Raw history coverage

Denominator is 278,220 eligible training applicants. Coverage means at least one raw
source row, before as-of verification. It does not certify completeness. Source-column
statistics scan the entire supplied history files, including rows outside this cohort.

| Source | Raw rows scanned | Applicants with rows | Raw coverage |
|---|---:|---:|---:|
| bureau | 1,716,428 | 238,709 | 85.80% |
| bureau_balance | 27,299,925 | 91,838 | 33.01% |
| previous_application | 1,670,214 | 264,656 | 95.12% |
| installments_payments | 13,605,401 | 265,264 | 95.34% |
| POS_CASH_balance | 10,001,358 | 263,059 | 94.55% |
| credit_card_balance | 3,840,312 | 85,498 | 30.73% |

Absent records must remain distinguishable from a verified empty source. In particular,
low bureau-balance/card coverage must not be interpreted as perfect repayment or no debt.

## Confirmed blockers and data issues

1. **Policy/manifest mismatch.** The existing RESEARCH override explicitly permits only
   Lite. Full also requires verified annuity semantics; the manifest retains the user's
   annual-income/monthly-annuity/unspecified-currency assumptions rather than verification.
2. **Historical availability is unverified.** All six history sources lack DAYS_AVAILABLE.
   Event dates or month offsets cannot simply be relabeled as knowledge-availability dates.
3. **No contractual installment schedule.** installment_schedule.csv is absent, and
   schedule completeness/effective-version resolution are false. Payment rows alone do
   not establish obligations with no recorded payment.
4. **Payment identity is unverified.** PAYMENT_ID is absent; identical-looking rows are
   not proof that events are duplicates. Reversals and schedule version semantics need
   reconciliation evidence before the existing adapter can accept normalized input.
5. **Source coverage evidence is absent.** None of the six manifest entries provides
   COMPLETE/CONFIRMED_EMPTY evidence. Raw presence percentages do not satisfy this gate.
6. **Unmapped bureau monthly history.** **3,120,184 rows (11.43%)** reference bureau IDs
   not mapped by the supplied bureau table. The existing Full aggregation rejects such
   unavailable/orphan balance accounts. A documented source-boundary/normalization rule
   is needed; no silent dropping was performed here.
7. **Missing bureau debt.** AMT_CREDIT_SUM_DEBT is missing in **15.0119%** of bureau rows;
   AMT_CREDIT_SUM is missing in **0.000757%**. The existing aggregation deliberately
   preserves unknown totals instead of summing partial known balances.
8. **Incomplete payment rows.** DAYS_ENTRY_PAYMENT and AMT_PAYMENT are each missing in
   **2,905 installment rows (0.02135%)**. These are not evidence of zero payment. Their
   source meaning must be resolved before canonical payment validation can pass.
9. **Negative balances need semantic review.** There are **8,418 negative bureau debt
   values** and **2,345 negative card balances**. These may represent account credits,
   adjustments or source conventions. They are not automatically corruption. Current
   card logic intentionally handles negative balances for utilization; Full disallows
   negative bureau debt aggregates, so affected borrower totals need explicit review.

No positive event offsets or invalid non-null numeric values were found in the selected
profile columns. This does not certify every CSV column or all duplicate/relational
keys. Full canonical validation could reveal additional issues after the current gates
are resolved. No real Full aggregate values or Full feature distributions are claimed.

## Implementation and validation

The new tool is outside `creditiq_ml`, so the pinned package and its 14 source hashes are
preserved. It calls existing `source_manifest`, `application_features`, `history_features`
and `validate_features`. Reports enumerate preflight failures; Full output is published
only after canonical aggregation and feature validation succeed. Existing output folders
are rejected to avoid stale successful datasets. The raw files and manifests are read-only.

The new tests cover normalized-fixture parity with the existing 60-feature builder,
training-only cohorts, missing evidence/schedules, future-payment filtering, invalid
labels, ownership failures, reproducible dataset hashes, output protection and the
blocked CLI exit code. They do not fit models. Final targeted suite: **31 passed in
34.38 seconds**, zero failures (9 new builder tests and 22 existing contract/history tests).

Pinned Lite loading succeeded: **9 artifact checksums and 14 source checksums match**;
latest remains **20261002T140817Z-045430a7**. No backend, frontend, authentication, schema,
database, deployment or Supabase changes were made in this milestone.

Initial test execution encountered Windows access restrictions on pytest's default
temporary directory; a workspace-local disposable basetemp resolved that. Tests also
identified a histogram edge issue for almost-constant floating-point ratios; the new
reporter now uses unique representable bin edges. The real run emitted a non-fatal pandas
fragmentation performance warning during application loading. It completed its reports
and returned a non-success status as intended for blocked Full readiness.

## Rerun

From `ml`, use a fresh output directory:

```powershell
.\.venv\Scripts\python.exe tools/full_dataset.py --raw-dir data/raw/DATASET_CREDITIQ --output-dir full_dataset_output/next-readiness
```

Python CLI exit codes: 0 = Full contract passed; 2 = audit completed but Full blocked;
1 = execution/input failure. Inspect build_manifest.json for authoritative readiness.

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_full_dataset.py tests/test_contracts.py tests/test_history.py -q -p no:cacheprovider --basetemp=.test-tmp-full-next
```

Use a new disposable basetemp directory. Streaming profiling has been run against all
real inputs. The accepted Full aggregation path was tested with normalized synthetic
fixtures only; its peak memory/performance at real-data scale is not yet validated.

## Training readiness and recommended next action

**Not ready to train Full under the existing contract.** The builder/reporting work is
complete; generation of the requested complete real Full dataset remains blocked.

Next, resolve source identity, schedule, availability and monetary semantics using
evidence-backed normalized inputs in a separate directory. Preserve the original files.
If the public dataset cannot supply that evidence, the alternative is a separately
reviewed research-specific Full contract with explicit limits and revised feature
definitions, not false verification flags. That contract change was not made here.
Do not train until the chosen path passes its agreed validation gates.
