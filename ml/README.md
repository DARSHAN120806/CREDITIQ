# CreditIQ ML — remediated Phase 1

The package remains in `ml/creditiq_ml`. Its authority is the root `CREDITIQ_DESIGN.md`.
Version 1.1 introduces incompatible `lite-v1` (17 semantic features) and `full-v1` (60 features).
**Retrain old models.** Legacy caches/artifacts are not migrated or silently served.

## Environment and tests

The project now has a local `.venv` for this machine. In PowerShell:

```powershell
Set-Location 'C:\Users\darsh\Downloads\creditiq_ml_phase1\ml'
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
.\.venv\Scripts\python.exe -m pytest tests -q
```

On a new machine, install Python 3.12 and create `.venv` first with
`py -3.12 -m venv .venv`. The original machine's launcher had no registered Python;
the current environment was created with the bundled Python runtime. Do not copy this
venv to another machine. `requirements.txt` pins direct dependencies;
`requirements-lock.txt` captures the tested Windows/Python 3.12 dependency set.

## Safe synthetic smoke run

Synthetic data is exclusively for plumbing/regression verification, not performance claims.
The generator refuses a nonempty destination. Use a new directory if one already exists.

```powershell
.\.venv\Scripts\python.exe tests/make_synthetic.py data/raw_synth_new --rows 800
.\.venv\Scripts\python.exe -m creditiq_ml.cli all --feature-set lite --raw-dir data/raw_synth_new --output-dir smoke_output --models logistic_regression decision_tree --trials 1 --tune-rows 500
.\.venv\Scripts\python.exe -m creditiq_ml.cli all --feature-set full --raw-dir data/raw_synth_new --output-dir smoke_output --models logistic_regression --trials 1 --tune-rows 500
```

The generator supplies a synthetic complete contractual schedule, payment IDs,
availability dates and a clearly marked synthetic manifest. Do not copy its evidence
flags into real-data manifests.

## Real-data preparation: mandatory evidence gates

Put the original Home Credit data in `data/raw`. Copy `adapter_manifest.example.json`
to `data/raw/adapter_manifest.json`, then record actual review evidence before changing
any false verification flags to true.

Lite requires confirmed cash-loan semantics, annual income/monthly annuity semantics,
verified category mappings and a declared three-letter monetary domain. `XXX` denotes
research/unspecified units, not rupees or an approved deployment currency.
Unresolved original outcome horizon and population suitability remain release gates.
The manifest is an audit declaration, not independent proof of those claims.

Full additionally requires all six history sources COMPLETE or CONFIRMED_EMPTY,
availability evidence, a resolved contractual schedule and reliable payment identity.
**The original eight CSVs alone do not establish these extra facts.**
Training fails explicitly instead of inventing them.

The normalized history adapter uses numeric dates relative to the applicant's cutoff
T=0. History tables must include `DAYS_AVAILABLE` in addition to their existing event
date/month columns. Providers must establish these dates; never assign arbitrary
negative dates merely to satisfy validation. Online callers convert their verified
timestamps to the same relative representation.

The supplementary `installment_schedule.csv` has these columns:

- SK_ID_CURR, SK_ID_PREV, NUM_INSTALMENT_NUMBER, NUM_INSTALMENT_VERSION
- DAYS_INSTALMENT, AMT_INSTALMENT, DAYS_AVAILABLE

It must contain the effective schedule, including never-paid obligations. One effective
version per loan/installment is allowed. Conflicting versions are rejected, not resolved
by taking the largest number. If a complete schedule cannot be established, full-v1
cannot be released; continue with Lite research and review routing.

The normalized `installments_payments.csv` additionally needs `PAYMENT_ID` and
`DAYS_AVAILABLE`. Repeated IDs with identical values are deduplicated; conflicting
duplicates fail. Missing event IDs, reversals without reconciliation, schedule conflicts,
or unknown payment dates fail. No event-ID synthesis from amount/date is performed.

All POS/card loan IDs must have a matching previous-application owner. Bureau balance
accounts must match available bureau accounts. Sources with unknown fields preserve
missing values; complete empty sources yield zero counts and undefined ratios.
Full data-quality errors fail the run rather than silently dropping inconvenient history.

## Rerun training

Once the real-data evidence gates are satisfied:

```powershell
.\.venv\Scripts\python.exe -m creditiq_ml.cli train --feature-set lite --raw-dir data/raw --models logistic_regression decision_tree random_forest xgboost lightgbm --trials 25 --no-cache
.\.venv\Scripts\python.exe -m creditiq_ml.cli explain --feature-set lite

.\.venv\Scripts\python.exe -m creditiq_ml.cli train --feature-set full --raw-dir data/raw --models logistic_regression decision_tree random_forest xgboost lightgbm --trials 25 --no-cache
.\.venv\Scripts\python.exe -m creditiq_ml.cli explain --feature-set full
.\.venv\Scripts\python.exe -m creditiq_ml.cli segment --feature-set full
```

Nested selection is more expensive than the original pipeline. For a development run,
select fewer models, use `--trials 1`, `--tune-rows 500`, and optionally
`--max-rows 1000`. These are exploratory releases, not production performance estimates.
Small/one-class cohorts fail explicitly. Use the same max-rows setting when comparing
Lite and Full partition identities.

`--no-cache` now works with train as well as features/all.
`--raw-dir` and `--output-dir` isolate real and synthetic experiments.
`--run-id <id>` selects a completed immutable release for explain/segment.
Do not use a Lite run ID for Full segmentation.

Explicit `eda` remains available for descriptive research:
`python -m creditiq_ml.cli eda --raw-dir data/raw`.
It reads all supplied training labels and should not drive iterative decisions about
a supposedly untouched holdout. For this reason, `all` no longer automatically runs EDA.

## Validation and model selection

Customer-disjoint partitions: 60% development, 15% calibration, 10% policy validation,
15% test, with explicit integer rounding and development receiving the remainder.
Shared Lite-eligible customer IDs establish comparable Lite/Full partitions.

Three development outer folds evaluate candidate model/calibrator pairs.
Within each outer fold, base-model fitting/tuning and calibration use disjoint subsets.
The outer assessment fold fits neither. Preprocessing and imbalance estimation are
fold-local; there is no global missingness feature drop. Candidate selection prioritizes
mean development Brier loss, then ROC-AUC. Final hyperparameters are tuned on development.

The selected base model is fitted on development only. Its chosen sigmoid/isotonic
calibrator is fitted on the separate calibration cohort. Policy-validation predictions
produce descriptive candidate-threshold tables, not an automatic live policy. Only
the frozen champion reaches the final test. Do not choose new settings after reading
test results and continue calling that same test an independent acceptance set.

Final results include AP, AUC, Gini, directional KS, Brier, log loss, sandbox-threshold
classification metrics, baselines, bootstrap intervals and band counts/outcomes.
The default policy remains sandbox; production thresholds are unset.

## Artifacts

Each successful run writes:

```text
artifacts/<lite|full>/runs/<run-id>/
  best_model.joblib
  metadata.json
  splits.json
  development_folds.json
  policy.json
  explanation_background.parquet
  explanation_sample.parquet
  development.parquet
  policy_validation.parquet
  test_predictions.parquet
artifacts/<lite|full>/latest.json
reports/training/<lite|full>/<run-id>/
  model_comparison.csv
  development_folds.csv
  policy_validation.json
  test_metrics.json
  risk_bands.csv
  roc_curves.png
  pr_curves.png
  calibration.png
```

Metadata includes exact semantic/transformed columns, source/code hashes, adapter
evidence, exclusion summaries, missingness, split sizes, calibrator, positive class,
runtime versions, release gates and artifact checksums. JSON forbids NaN.
The latest pointer is atomically published only after a completed release.
Load only trusted local/registry joblib artifacts; `load_model` verifies file checksums
but checksums do not authenticate an attacker-controlled registry.

Feature caches are variant/content-specific and verify their parquet hash.
Detailed row exclusions are in the corresponding processed feature JSON report.
Applicant-level artifacts are sensitive research data; do not publish them.

## Serving contract

`CreditRiskModel.predict_proba` intentionally retains the old one-dimensional positive-PD
interface, but now accepts only validated complete canonical feature vectors.
Missing mandatory fields and inconsistent derived values fail.

`score_request` is the raw request entry point. It validates the application metadata,
canonical fields and a trusted server-issued quote, then invokes the shared feature code.
A quote must supply matching application/quote IDs, version, currency, amount, monthly
payment and timezone-aware expiry. Authentication, quote retrieval and product limits
remain responsibilities of the future application service.

Full `score_request` additionally accepts normalized raw history DataFrames, the effective
schedule, and trusted source_context containing the manifest gates/source evidence,
customer_id and the matching as_of timestamp. It computes the same aggregates as training;
applicants cannot supply a favorable precomputed bureau score instead.

Support flags identify unseen categories/missingness and numeric values outside the
development range. Such flags prevent automatic decisions. These checks are a basic
support screen, not a complete out-of-distribution detector.

## Policy behavior

Risk score = 100 * calibrated PD. Display bands use unrounded PD:
Low <5%, Medium >=5% and <15%, High >=15%.
A rounded display score never determines a band.
The CreditIQ health index is 100*(1-PD), not the old bureau-like 300-850 scale.

Sandbox returns APPROVAL_CANDIDATE / MANUAL_REVIEW / REJECTION_CANDIDATE, while final
decision_status stays MANUAL_REVIEW. Live policy objects require ordered thresholds,
model/version binding and independent approval evidence. Lite, unsupported/unverified
inputs, unreleased models, and missing affordability cannot auto-approve. All trained
bundles currently remain RESEARCH_ONLY/release_ready=false: this remediation does not
certify or activate a lending policy.

## SHAP and segmentation

SHAP explains base-model output, not the post-calibration probability. It records
raw-margin versus uncalibrated-probability units, reference source, model/schema version,
positive class, calibrated PD separately, omitted-feature remainder and additivity error.
Attribution share is not a probability percentage-point effect.
Background data is development-only; tree path reference uses the fitted training trees.

Segmentation requires Full. It fits and persists log transforms, clipping bounds,
imputation and scaling on development only; tests k=2..7 with sampled silhouette,
minimum size and repeated-seed stability. It fails if no acceptable clustering exists.
Labels are descriptive Segment 1/2/etc., never automatic Prime/High Risk decisions.
Assessment uses the policy cohort; final test is not consumed by segmentation.

See root CHANGELOG.md and VALIDATION_CHECKLIST.md for the change inventory and release gates.

## FULL_RESEARCH_V1 application-snapshot dataset

`research_contracts/FULL_RESEARCH_V1.json` is a separate 28-feature research schema. It
reuses the application transformation for the inherited Lite features, then derives
scores/inquiry ratios from the same Home Credit application snapshot. It deliberately
excludes all 43 linked-history Full features until event-time availability, mapping and
payment/schedule evidence can be established. Existing Full/Lite contracts are unchanged.

Build from `ml` into a new empty directory:

```powershell
.\.venv\Scripts\python.exe tools/full_research_v1.py --raw-dir data/raw/DATASET_CREDITIQ --output-dir research_output/full_research_v1/next-run
```

The output contains `full_research_v1_train.parquet`, a copy of the exact contract,
feature inventory, missingness and coverage CSVs, distributions, excluded history
features and a SHA-256 build manifest. TARGET and SK_ID_CURR are separate from the
contract's 28 predictors. Missing values are preserved; do not preprocess on the full
dataset. Training, calibration and policy thresholds remain a later, separate step.
The generated parquet and build outputs are ignored; the source contract, builder and
root readiness report are versioned. A rerun requires all seven input CSVs and the
research assumptions in `adapter_manifest.json` to match this contract.

## Full dataset readiness builder (no training)

The separate `tools/full_dataset.py` command reuses the existing canonical contract,
application transformation and Full history aggregation. It does not edit pinned
`creditiq_ml` source, artifacts, manifests, raw CSVs or Lite output. It uses only
`application_train.csv` as the applicant cohort; competition test is excluded.

From `ml`, select a new, empty output directory on each run:

```powershell
.\.venv\Scripts\python.exe tools/full_dataset.py --raw-dir data/raw/DATASET_CREDITIQ --output-dir full_dataset_output/next-readiness
```

Exit codes: **0** = Full dataset contract validated; **2** = reports produced but
Full contract blocked; **1** = build execution/input failure. Existing nonempty output
directories are rejected to prevent accidentally retaining stale successful datasets.

Outputs include `build_manifest.json`, `FULL_FEATURE_REPORT.md`, `feature_quality.csv`,
`feature_distributions.json`, `source_coverage.csv`, `source_column_quality.csv`,
`source_categories.json` and `excluded_applications.csv`. A blocked run writes only
`application_features_ONLY_NOT_FULL.parquet`; it must not be used as a Full dataset.
Only a gate-passing, canonically validated run writes `full_features.parquet`.
Raw coverage measures applicants with source rows, not verified historical availability.
No values are imputed and no estimators are fitted. Source/code/output hashes are saved.

The current research override applies only to Lite. Do not mark availability, payment
identity or schedule completeness verified simply to unlock Full. The original payment
file does not establish the entire schedule, including never-paid installments.

Dataset-only regression checks (no model-training tests):

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_full_dataset.py tests/test_contracts.py tests/test_history.py -q -p no:cacheprovider --basetemp=.test-tmp-full-next
```

Use a new disposable basetemp path; pytest may clear an existing basetemp directory.
Raw profiling streams CSV chunks. The verified Full path reuses the existing in-memory
aggregations and requires sufficient RAM for normalized history tables; full-scale
memory performance is not certified by the small synthetic contract tests.

