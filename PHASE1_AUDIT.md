# CreditIQ Phase 1 technical audit

Review date: 2 October 2026. Scope: the extracted `ml/` project supplied in this workspace. This is a source audit, not a certification of predictive performance. No application or ML implementation was changed.

## Verdict

**Keep and repair this project. It is a useful research scaffold, but it is not ready for application integration or lending decisions.** All five claimed classifiers, GridSearchCV, Optuna, calibration, SHAP, and KMeans exist in source. Their presence does not establish that training completed successfully or that the resulting models are valid.

The main blockers are the form-to-model contract, payment aggregation semantics, validation reuse, incomplete serving transformations, misleading explanation units, and non-reproducible segmentation. Real-data validation is still required.

### Evidence and limits

- Reviewed the README, dependency manifest, all 12 Python package files, and the synthetic-data generator. Source references below use paths relative to this workspace and original line numbers.
- The supplied workspace contains the extracted project. The named ZIP was not available at the expected sibling path; ZIP integrity and parity with this extraction could not be checked.
- No CSV data, trained joblib files, metadata, evaluation results, or generated plots were found in the project inventory. Expected output files are code paths, not verified deliverables.
- The `python` command is unavailable in the shell. No dependency installation, synthetic run, real-data training, or runtime compatibility test was performed. Findings marked confirmed follow directly from source; performance, data prevalence, memory consumption, and dataset-specific incidence remain unmeasured.
- There is no automated assertion suite. `tests/make_synthetic.py` generates data; it does not test correctness.

## Findings requiring action

| ID | Severity | Evidence | Finding and required correction |
|---|---|---|---|
| A01 | Blocker | `ml/creditiq_ml/config.py:32–42`; `model_wrapper.py:21–25` | Lite requires 26 engineered/raw fields, many absent from the proposed form. Missing columns are silently added as NaN. Define a supported input contract, build features from it, and retrain Lite on exactly those semantics. Reject missing mandatory inputs before prediction. |
| A02 | Blocker | `features.py:201–207`; `model_wrapper.py:21–35` | Training sanitizes category strings, but serving does not invoke sanitization or application feature engineering. For example, `Secondary / secondary special` becomes `Secondary_secondary_special` in training; the unsanitized value is unknown at inference. Ship one versioned transformer used by both paths. |
| A03 | High | `features.py:131–152` | Installment metrics count payment rows. Split payments can inflate late/underpaid counts and distort delay and payment ratios. Aggregate to contractual installment first, reconcile schedule versions and payments, and calculate completion/overdue status as of the decision date. |
| A04 | High | `train.py:175–199` | Validation labels fit isotonic calibration, optimize F1 threshold, and rank models by calibrated validation AUC. These are not independent validation results. Use out-of-fold calibration plus separate selection/policy evaluation, or explicit calibration and policy-validation partitions. Keep final test sealed until all choices are fixed. |
| A05 | High | `train.py:178–179`; `model_wrapper.py:41–46` | Portfolio prevalence becomes automatic approval threshold and F1 selects rejection. Neither encodes affordability, costs, exposure, or review capacity. No invariant ensures `approve_below < reject_at`; rejection has precedence if thresholds overlap. Replace with independently versioned, validated decision policy. |
| A06 | High | `explain.py:59–65,84–90` | SHAP targets the uncalibrated classifier. `base_value_logodds` is wrong for sklearn decision trees/random forests whose native explanations use probability output; logistic/boosting output differs. `impact_pct` is share of absolute attribution, not change in default probability. Store explicit explained output/units and calibration disclaimer; never render these as probability percentage points. |
| A07 | High | `segmentation.py:33–37,72–73` | Quantile clipping is learned but bounds are not saved. Serving cannot reproduce training preprocessing from `segmenter.joblib`. Persist log transform, clipping bounds, imputer, scaler, feature order, model, and label mapping together. |
| A08 | High | `features.py:210–214`; `cli.py:21–25` | Cache has no data/code/schema fingerprint. `train --no-cache` does not pass the flag through to `train_all`, so it still loads a cache. Stale or synthetic features can silently become training input. Make cache provenance explicit and make rebuild behavior consistent. |
| A09 | High | `features.py:33,69–78,113,137,156–157,238` | No enforced source-key uniqueness, relationship validation, conflicting duplicate checks, or as-of cutoff. Application duplicates are silently discarded; relational duplicates remain. Add table contracts, validated merges and temporal checks. Actual future-data leakage is unproven without CSVs. |
| A10 | Medium | `features.py:116–124` | `PREV_LOAN_COUNT` counts all previous applications, including refused/cancelled ones. Rename to previous application count; derive booked/disbursed loan count only from a reliable definition. Approved applications alone do not prove disbursement. |
| A11 | Medium | `features.py:182–197`; `config.py:40–41` | Utilization is historical mean of clipped account-month ratios, not current utilization. A user's single card-usage input is not an equivalent feature. Remove this proxy from Lite or acquire matching historical information and validate it. |
| A12 | Medium | `features.py:57,62,89–98,242` | All-missing products can become 1; all-missing sums can become 0. Enquiry windows are overlapping and should not be summed as independent events. Preserve unknown values and distinguish source unavailable, no records, and measured zero. |
| A13 | Medium | `segmentation.py:39–55` | Elbow/silhouette plots do not select k: the final model always uses supplied/default k=3. Cluster names are assigned using labels from all labeled applicants, including classifier holdout applicants. Keep this descriptive only; use separate discovery/validation cohorts before making risk claims. |
| A14 | Medium | `segmentation.py:40–44` | Six silhouette calculations use up to 20,000 rows without a smaller silhouette sample. Pairwise work can be expensive; small or degenerate inputs also fail. Bound sample size and validate row count, distinct points and cluster sizes. |
| A15 | Medium | `requirements.txt`; `train.py:237–245` | Dependencies have lower bounds only. Artifacts lack immutable version, source hashes, environment lock, split IDs, schema hash, and calibrator provenance. Add reproducible builds and a signed/checksummed release manifest. |
| A16 | Medium | `preprocessing.py:33–45`; `train.py:162–171` | Missingness-based feature selection happens outside inner CV; XGBoost class ratio is computed from outer training labels. Inner CV is not entirely fold-local. Move data-dependent selection and class-ratio estimation into fold fitting. Outer holdout preprocessing remains separate. |
| A17 | Medium | `preprocessing.py:42–45` | Every numeric variable is clipped at the 1st/99th percentiles. This can erase rare binary flags and extreme delinquency signals. Use feature-specific transformations with ablation evidence; exclude identifiers/flags and retain meaningful extremes. |
| A18 | Medium | `risk.py:6–14` | Bands ignore their lower bounds. Actual cutoffs are score <31, <61, otherwise High. Negative scores become Low and NaN/out-of-range values can be misclassified. Validate finite p in [0,1], use continuous probability cutoffs, and round only for display. |
| A19 | Medium | `features.py:249` | Adding bureau and POS active-loan counts does not establish a deduplicated total across sources. Even where source scopes are disjoint, definitions differ. Document scopes and avoid claiming a universal total without reconciliation. |
| A20 | Medium | `eda.py:120–128`; `train.py:245`; `explain.py:98–99` | EDA uses all labeled data and saved SHAP samples come from test. Descriptive EDA and explanations are not themselves model-fit leakage, but feature choices made after inspecting test labels compromise final-test independence. Reserve a development-only analysis cohort. |

## Architecture and maintainability

The separation into I/O, features, preprocessing, training, explanation, segmentation and scoring is sensible. A CLI and centrally defined paths make a first run understandable. Type hints and docstrings are helpful but partial.

Missing elements: package/build metadata, locked environments, structured configuration with validation, automated tests, CI, schema contracts, artifact registry, immutable runs, operational inference module, exception/recovery strategy, and performance budgets. Optional tables silently disappearing can produce materially different models with the same feature-set name. A missing whole source must be reflected in a declared feature contract rather than just a warning.

`io.py:23–27` downcasts every float64 to float32 without measuring error. This is a memory optimization, but cent-level payment comparisons require precision checks. Full CSV reads, dense one-hot arrays, retention of all five fitted models, and unrestricted estimator threads need profiling on the real dataset. Do not assume the README's synthetic runtime predicts full-data runtime.

Other correctness/robustness issues:

- `_named_agg` skips missing columns, but callers subsequently access several aggregate names unconditionally. Its advertised tolerance is incomplete.
- Sanitizing category strings can collapse distinct values (punctuation/whitespace variants). Use reversible or explicitly enumerated category normalization and collision checks.
- Latest POS row selection has no deterministic tie policy and assumes nonmissing month indices.
- `CREDIT_TERM = annuity / credit` is a repayment-burden proxy, not term in months.
- Artifact writes overwrite prior releases and are not atomic. Metadata lists all pre-filter features rather than only those consumed by the fitted transformer.
- `predict_proba` returns a one-dimensional positive-class vector, unlike the standard sklearn two-column convention. Document or rename the interface and explicitly persist the positive class.
- `segment(sample=...)` declares but does not use `sample`; CLI numeric parameters lack range validation.

## Verification of the seven requested features

| Feature | Existing calculation | Assessment / correct contract |
|---|---|---|
| Debt-to-Income Ratio | `AMT_ANNUITY / (AMT_INCOME_TOTAL / 12)` | Correct as proposed-loan payment-to-income **if annuity is monthly and income annual in matching currency**. It excludes existing obligations, so it is not total DTI. Total DTI needs `(existing monthly debt payments + proposed monthly payment) / verified monthly income`. Confirm units in the data dictionary and product definition. |
| Credit Utilization Ratio | Per-row balance/limit, clipped 0–2; mean/max per customer | A defensible historical descriptor after duplicate/time validation; not current weighted utilization. Current usage should select latest valid snapshot per account then compute sum(balance)/sum(limit), with explicit zero/missing-limit policy. Keep historical mean under an honest name. |
| Late Payment Count | Sum of `payment_date > due_date` across payment rows | Not verified at installment grain. Group by customer/loan/installment/schedule version after resolving schedule changes. Determine when cumulative payments satisfy amount due. Count each installment once; handle unpaid overdue installments as of cutoff. |
| Previous Loan Count | Count of `SK_ID_PREV` in previous applications | Misnamed; includes refused and cancelled applications. Count unique applications, approved applications, and actual booked loans separately. |
| Previous Rejection Count | Sum of `NAME_CONTRACT_STATUS == Refused` | Correct for refused application rows if one row per application and statuses are complete. Deduplicate/validate keys; do not count cancellation as refusal. |
| Active Credit Count | Sum of bureau `CREDIT_ACTIVE == Active` | Correct for active bureau accounts if each bureau ID is unique and status is current at cutoff. Does not necessarily equal the user's total existing loans or monthly debt burden. |
| Average Installment Delay | Mean of signed payment-date minus due-date | Valid as mean signed payment-row delay only. Early payments offset late ones and split payments distort weighting. Publish installment-level signed delay, overdue days, and late-only mean as separate measures; define treatment of unresolved payments. |

Example: an installment of 100 paid as 50 before its due date and 50 after it is one late installment, not two underpaid installments. Two late partial payments are still one late installment. These are mandatory regression fixtures before accepting the repaired aggregation.

Bureau/POS/card aggregates are generally grouped on the right customer key and bureau balance is aggregated by bureau loan before joining. This is good structure. However, row-weighted monthly means give longer histories greater weight; define whether account-weighted or month-weighted measures are intended. The `BB_SEVERE` comment says 60+ days while the status mapping must be checked against the dataset bucket definitions; do not use the comment as a business definition.

## Leakage, evaluation, and calibration

### What is already correct

- Target, customer ID, and `IS_TRAIN` are excluded from classifier features.
- A stratified 70/15/15 split is implemented. Unlabeled `application_test` rows are filtered out before fitting.
- Clipping, imputation and one-hot encoding are pipeline steps refitted inside tuning folds. Logistic regression is additionally standardized.
- Concatenating train and competition-test rows for deterministic row-local calculations and customer-key aggregations is **not automatically leakage**. Here it still needs disjoint IDs, valid table keys, and decision-time availability checks.
- Class weights are present for all five classifiers. No oversampling is performed before splitting.
- Calibration data is separate from base-model fitting data. This is a sound starting point; the subsequent reuse for selection is the problem. See [scikit-learn calibration guidance](https://scikit-learn.org/stable/modules/calibration.html).
- Winner selection is based on validation, not test AUC. Nevertheless all candidates' test results are exposed, so later human selection must not use them.

### Metric correctness

Accuracy, precision, recall, F1, ROC-AUC, `Gini = 2*AUC - 1`, Brier score and clipped log loss are implemented conventionally. KS is maximum TPR minus FPR, a standard directional credit-score separation measure; it is not a general two-sided KS statistic. `PR_AUC` is actually **average precision**, not trapezoidal area under the precision-recall curve. Rename it `AveragePrecision` and document the integration convention.

F1 thresholds are not underwriting economics. Accuracy must be compared with an always-nondefault baseline; AP with positive prevalence; Brier/log loss with constant-prevalence predictions. Add confidence intervals, band counts/default rates, lift/recall at review capacity, calibration intercept/slope/reliability by cohort, and expected-loss analyses only after exposure and loss definitions exist. Validate both classes exist in each evaluation partition and report undefined metrics explicitly.

Isotonic can overfit small calibration sets and create tied predictions. Compare sigmoid and isotonic with independent validation and report calibration stability, not just AUC. The fixed clip to [0.0001, 0.9999] should be recorded as a serving transformation. Do not interpret weighted classifier scores as calibrated PD before calibration.

Recommended experiment sequence: validate raw contracts and customer boundaries; reserve final test IDs; tune pipelines on development folds; select candidate and calibrator using out-of-fold predictions/disjoint calibration data; choose policy on independent validation predictions; freeze everything; evaluate final test once. For sufficiently large data, separate train/tune, calibration, policy-validation and test cohorts explicitly. For future lending data, use application timestamps and outcome maturity; relative Home Credit date fields do not by themselves establish a valid chronological portfolio split.

The code/data package does not establish a probability horizon, production population, currency conversion, or default-event definition. Until the original dictionary and outcome process are validated, use “model-estimated probability of dataset TARGET=1”; do not invent “12-month PD.” Consult the [original competition](https://www.kaggle.com/competitions/home-credit-default-risk) and its data dictionary before fixing product terminology.

## SHAP review

Positive attributions are correctly presented as factors increasing default-model output; negative attributions reduce it. Transforming data with the fitted pipeline before explaining its classifier is appropriate, including scaling for logistic regression. Summing one-hot attributions back to source fields is reasonable, but prefix matching should be replaced by encoder-derived mappings and tested for name collisions.

Required explanation contract: model version, feature version, explainer version, reference cohort, target class, explained output (`raw_margin`, `uncalibrated_probability`, or `calibrated_probability`), base value, feature contributions, residual/other contribution, and additivity check. [SHAP's TreeExplainer documentation](https://shap.readthedocs.io/en/latest/generated/shap.TreeExplainer.html) distinguishes raw and probability outputs; they cannot share a hardcoded log-odds label.

For the first release, explain the base model transparently and show calibrated PD separately. A separate model-agnostic explainer can target the complete calibrated function if probability-space attribution is required, subject to measured latency and approximation checks. Do not multiply raw SHAP values by 100 and call them percentage-point effects.

Persist a development-derived background rather than rebuilding it from test. The supplied background is used by LinearExplainer but is not passed into TreeExplainer. Test modern SHAP output shapes and positive-class selection against pinned versions. Explanations describe model associations, not causal guarantees or instructions that changing a field will secure approval. Avoid personal “credit advice” based on age, gender, or other non-actionable attributes.

## KMeans review

Log transforms for income/credit, median imputation and StandardScaler are good choices to investigate. The target is not in the clustering feature matrix. PCA is only a visualization, not the clustering space.

The model is exploratory: k=3 is a product choice, not a validated optimum; there is no stability or holdout assessment. Select k using silhouette, inertia, minimum size, repeated-seed stability and interpretability. Bound silhouette calculation with a sample; [scikit-learn provides a `sample_size` parameter](https://scikit-learn.org/stable/modules/generated/sklearn.metrics.silhouette_score.html).

Fit all segmentation transformations on the discovery cohort, persist them, and evaluate held-out segment assignments and outcome rates with intervals. Version the label mapping. “Prime” is not justified merely by being the lowest-risk of three clusters: all clusters could have high absolute risk. Prefer descriptive segment names until validated; keep segments independent of PD bands and approval policy. Do not force Lite-only applicants into the Full-history segmenter by median-filling most history fields; show unavailable or train a separate supported segmenter.

## Risk scoring decision

`risk_score = 100 * calibrated_probability` is mathematically sound as a display transformation. It is a percentage-like risk index, not an independent credit score. The current 30/60 proposal cannot be validated without real held-out predictions; low prevalence alone does not prove its exact band shares. It is likely too coarse for useful portfolio differentiation and has inconsistent continuous boundaries in code.

### Option A: absolute probability bands

Illustrative development-only scheme: Low `0 <= p < 0.05`, Medium `0.05 <= p < 0.15`, High `0.15 <= p <= 1`. Thus 5% is Medium and 15% is High, with no gaps. **These numbers are examples, not approved thresholds.** Derive real cutoffs from independent calibrated predictions, observed band outcomes/confidence intervals, product economics, target population and risk appetite. Store thresholds by model/product/policy version and never let a live dashboard recompute them.

Advantages: stable absolute interpretation and drift visibility. Weaknesses: depends on calibration and population validity; may produce uneven or empty bands.

### Option B: reference-percentile bands

Illustrative scheme: lowest 60% of PDs in a frozen reference cohort = Low relative risk, next 30% = Medium relative risk, highest 10% = High relative risk. Fit the quantile boundaries on development/approved reference predictions, not the final test set or current request batch. Version the reference cohort, dates, model and quantile method. Preserve tied PDs in the same band even if exact 60/30/10 shares cannot be achieved.

Advantages: useful for ranking, triage and review-capacity planning. Weaknesses: ranks are relative; top decile does not mean 10% PD and a low percentile does not mean affordable or safe. Recomputing percentiles on each batch can conceal population deterioration.

### Recommendation

Use **calibrated absolute PD and validated absolute bands for customer risk displays**, plus a **separate frozen-reference percentile for admin prioritization**. Use an independently versioned policy for Approved / Manual Review / Rejected, including data sufficiency, affordability and product rules. Keep unsupported or out-of-distribution applicants in manual review rather than imputing confidence. A Lite score should be provisional until information is verified.

The existing 300–850 `credit_health_score` is a monotone good-odds transform: 600 points at good:bad odds 50:1, +40 per doubling, clipped to 300–850. The docstring's “1:50” is ambiguous. It is not a bureau score and requires its own validation/presentation decision. Prefer a clearly branded “CreditIQ estimate”; do not imply an official credit score. Never display an eligibility recommendation or loan amount as a consequence of PD alone.

## Production readiness summary and release gates

**Good:** modular research package, stratification, fold-fitted preprocessing, class weighting, baseline/tree/boosting comparisons, separate calibration fit, probability metrics, explanation grouping, and scaled clustering.

**Weak:** unverified data/artifacts, semantic errors, inference mismatch, validation reuse, permissive missing inputs, mutable caches/releases, no assertion suite, no serving contract, no independent policy engine, no reliable population/horizon definition.

**Unnecessary for the first deployment:** serving all five classifiers, running both tuning frameworks online, retraining from an HTTP request, making KMeans mandatory for approvals, and building a feature-store platform or microservice fleet before traffic warrants it. Keep benchmark models offline; deploy one validated champion per supported feature contract.

**Required before FastAPI/Next.js implementation begins:** agree on the architecture/input contracts in the companion document and record unresolved business definitions. Before model integration: repair A01–A09, add semantic fixtures, train against real data, and release a reproducible Lite/Full bundle. Before a live lending pilot: verify target/horizon/population suitability, cohort performance and calibration, consent/data access, affordability policy, access control, auditability and outcome monitoring. Gender and similar attributes should default to excluded from scoring pending the intended jurisdiction's feature policy; collect for restricted fairness evaluation only when appropriate. No jurisdiction-specific legal conclusion is made here.

Acceptance checks should include split-payment fixtures, duplicate/conflicting IDs, future records, missing-source versus no-history cases, zero limits/income, unknown categories, train/serve feature equality, full serialization parity, calibration/threshold independence, threshold boundaries, SHAP units/additivity, segmenter reload parity, and a reproducible end-to-end real-data run. Synthetic accuracy is not evidence of lending utility.

See `ARCHITECTURE_REVIEW.md` for the proposed system diagram, full application layout, schema, ER diagram, endpoint contract and Lite/Full serving design.
