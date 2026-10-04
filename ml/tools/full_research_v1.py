"""Build a separate application-snapshot research contract; never trains a model."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd

ML_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ML_ROOT.parent
sys.path.insert(0, str(ML_ROOT))
from creditiq_ml.contracts import LITE_FEATURES, CATEGORICAL, HISTORY_GROUPS, ContractError, validate_features
from creditiq_ml.features import application_features
from creditiq_ml.provenance import sha256, write_json

CONTRACT_VERSION = "FULL_RESEARCH_V1"
APP_EXTRAS = ["EXT_SOURCE_1", "EXT_SOURCE_2", "EXT_SOURCE_3",
              "ext_source_1_missing", "ext_source_2_missing", "ext_source_3_missing",
              "credit_bureau_inquiries_1m", "credit_bureau_inquiries_3m",
              "credit_bureau_inquiries_12m", "credit_bureau_inquiry_history_missing",
              "loan_to_goods_price_ratio"]
FEATURES = LITE_FEATURES + APP_EXTRAS
CONTRACT_PATH = ML_ROOT / "research_contracts" / "FULL_RESEARCH_V1.json"
SOURCES = {
    "application_train.csv": "application_train",
    "bureau.csv": "bureau", "bureau_balance.csv": "bureau_balance",
    "previous_application.csv": "previous_application",
    "installments_payments.csv": "installments_payments",
    "POS_CASH_balance.csv": "pos_cash_balance", "credit_card_balance.csv": "credit_card_balance",
}
EXT_SCORES = ["EXT_SOURCE_1", "EXT_SOURCE_2", "EXT_SOURCE_3"]
ENQUIRY_MAP = {"credit_bureau_inquiries_1m": "AMT_REQ_CREDIT_BUREAU_MON",
               "credit_bureau_inquiries_3m": "AMT_REQ_CREDIT_BUREAU_QRT",
               "credit_bureau_inquiries_12m": "AMT_REQ_CREDIT_BUREAU_YEAR"}

HISTORY_DEFS = {
    "bureau_account_count": "Distinct bureau credit accounts linked to the applicant.",
    "bureau_active_count": "Linked bureau accounts marked Active.",
    "bureau_closed_count": "Linked bureau accounts marked Closed.",
    "bureau_overdue_count": "Bureau accounts with positive reported CREDIT_DAY_OVERDUE.",
    "bureau_total_credit": "Sum of reported AMT_CREDIT_SUM across linked accounts.",
    "bureau_total_debt": "Sum of reported AMT_CREDIT_SUM_DEBT across linked accounts.",
    "bureau_total_overdue": "Sum of reported AMT_CREDIT_SUM_OVERDUE across linked accounts.",
    "bureau_max_dpd": "Maximum reported account days past due.",
    "bureau_oldest_account_age_days": "Largest age in days derived from negative DAYS_CREDIT.",
    "bureau_newest_account_age_days": "Smallest age in days derived from negative DAYS_CREDIT.",
    "bureau_observed_status_months": "Count of bureau-balance months with status 0–5.",
    "bureau_delinquent_months": "Count of bureau-balance months with status 1–5.",
    "bureau_severe_months": "Count of bureau-balance months with status 3–5.",
    "bureau_late_month_ratio": "Bureau delinquent months divided by observed status 0–5 months.",
    "previous_application_count": "Count of prior-loan applications by SK_ID_PREV.",
    "previous_approved_count": "Count of prior applications marked Approved.",
    "previous_refused_count": "Count of prior applications marked Refused.",
    "previous_refusal_rate": "Refused applications divided by prior applications.",
    "previous_applications_365d": "Prior application decisions dated within 365 days of current application.",
    "days_since_previous_application": "Age in days of the most recent prior application decision.",
    "installment_due_count": "Effective contractual installments due by application cutoff.",
    "installment_fully_paid_count": "Effective installments whose reconciled cumulative payments cover the amount due.",
    "installment_late_count": "Due installments completed late or unpaid after due date.",
    "installment_unpaid_overdue_count": "Due installments unpaid as of cutoff.",
    "installment_late_rate": "Late installments divided by due installments.",
    "installment_mean_signed_delay": "Mean completed payment delay in days; early payment is negative.",
    "installment_mean_overdue_days": "Mean overdue duration in days across due installments.",
    "installment_max_overdue_days": "Maximum overdue duration in days.",
    "installment_mean_paid_ratio": "Mean of cumulative paid amount divided by scheduled amount, capped at one.",
    "pos_loan_count": "Distinct prior POS/cash accounts.",
    "pos_active_loan_count": "POS/cash accounts whose latest snapshot is Active.",
    "pos_observed_months": "Count of POS/cash account-month snapshots.",
    "pos_max_dpd": "Maximum POS/cash SK_DPD.",
    "pos_mean_dpd": "Mean POS/cash SK_DPD.",
    "pos_late_month_ratio": "POS/cash snapshots with positive SK_DPD divided by observed snapshots.",
    "card_account_count": "Distinct prior credit-card accounts.",
    "card_current_balance": "Sum of latest balances for active card accounts.",
    "card_current_limit": "Sum of latest credit limits for active card accounts.",
    "card_current_utilization": "Active latest balances divided by active latest valid limits.",
    "card_historical_mean_utilization": "Mean card balance-to-limit ratio across historical snapshots.",
    "card_historical_max_utilization": "Maximum card balance-to-limit ratio across historical snapshots.",
    "card_max_dpd": "Maximum reported card SK_DPD.",
    "card_late_month_ratio": "Card snapshots with positive SK_DPD divided by observed snapshots.",
}
APP_EXTRA_DEFS = {
    "EXT_SOURCE_1": "Raw normalized external-source score 1 as recorded on the application.",
    "EXT_SOURCE_2": "Raw normalized external-source score 2 as recorded on the application.",
    "EXT_SOURCE_3": "Raw normalized external-source score 3 as recorded on the application.",
    "ext_source_1_missing": "Indicator that EXT_SOURCE_1 is missing on the application.",
    "ext_source_2_missing": "Indicator that EXT_SOURCE_2 is missing on the application.",
    "ext_source_3_missing": "Indicator that EXT_SOURCE_3 is missing on the application.",
    "credit_bureau_inquiries_1m": "AMT_REQ_CREDIT_BUREAU_MON: inquiries in prior month excluding prior week.",
    "credit_bureau_inquiries_3m": "AMT_REQ_CREDIT_BUREAU_QRT: inquiries in prior three months excluding prior month.",
    "credit_bureau_inquiries_12m": "AMT_REQ_CREDIT_BUREAU_YEAR: inquiries in prior year excluding prior three months.",
    "credit_bureau_inquiry_history_missing": "Indicator that all six source bureau-inquiry windows are absent.",
    "loan_to_goods_price_ratio": "AMT_CREDIT divided by positive AMT_GOODS_PRICE.",
}
LITE_DEFS = {
    "age_years": "-DAYS_BIRTH / 365.25.",
    "years_employed": "-DAYS_EMPLOYED / 365.25; Home Credit sentinel 365243 is missing.",
    "annual_income": "AMT_INCOME_TOTAL; annual period is an authorized research assumption.",
    "requested_amount": "AMT_CREDIT from current cash-loan application.",
    "quoted_monthly_payment": "AMT_ANNUITY; monthly period is an authorized research assumption.",
    "household_size": "CNT_FAM_MEMBERS.", "dependent_children": "CNT_CHILDREN.",
    "employment_type": "NAME_INCOME_TYPE mapped to existing canonical category vocabulary.",
    "education_level": "NAME_EDUCATION_TYPE mapped to existing canonical category vocabulary.",
    "occupation": "OCCUPATION_TYPE mapped to canonical vocabulary; null becomes MISSING.",
    "housing_status": "NAME_HOUSING_TYPE mapped to canonical vocabulary; null becomes MISSING.",
    "employment_tenure_missing": "1 when normalized years_employed is missing; otherwise 0.",
    "proposed_payment_income_ratio": "quoted_monthly_payment / (annual_income / 12).",
    "principal_income_ratio": "requested_amount / annual_income.",
    "income_per_household_member": "annual_income / household_size.",
    "employed_age_ratio": "years_employed / age_years.",
    "payment_principal_ratio": "quoted_monthly_payment / requested_amount.",
}


def build(raw_dir: Path, output_dir: Path):
    raw_dir, output_dir = raw_dir.resolve(), output_dir.resolve()
    if not raw_dir.is_dir() or raw_dir == output_dir or raw_dir in output_dir.parents:
        raise ValueError("Raw directory must exist and output must be a separate location")
    if output_dir.exists() and any(output_dir.iterdir()):
        raise ValueError("Choose a new empty output directory")
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = {name: raw_dir / name for name in SOURCES}
    missing = [name for name, path in paths.items() if not path.is_file()]
    if missing:
        raise ValueError(f"Required source files missing: {missing}")
    # Reuse the prior full raw audit; verify its inputs still identify these files.
    prior = REPO_ROOT / "ml/full_dataset_output/20261004-readiness-v1/build_manifest.json"
    manifest_path = raw_dir / "adapter_manifest.json"
    if not manifest_path.is_file():
        raise ValueError("adapter_manifest.json is required to identify the authorized research assumptions")
    adapter = json.loads(manifest_path.read_text(encoding="utf-8"))
    assumptions = adapter.get("research_assumptions", {})
    if (adapter.get("mode") != "RESEARCH" or adapter.get("release_ready") is not False or
            assumptions.get("income_period") != "annual" or assumptions.get("annuity_period") != "monthly" or
            assumptions.get("currency") != "unspecified_research_currency"):
        raise ContractError("Adapter manifest does not match the authorized research assumptions")
    source_hashes = {name: sha256(path) for name, path in paths.items()}
    source_hashes[manifest_path.name] = sha256(manifest_path)
    dictionary_path = raw_dir / "HomeCredit_columns_description.csv"
    if dictionary_path.is_file():
        source_hashes[dictionary_path.name] = sha256(dictionary_path)
    if prior.exists():
        prior_manifest = json.loads(prior.read_text(encoding="utf-8"))
        for key, name in SOURCES.items():
            if key in prior_manifest["input_sha256"] and prior_manifest["input_sha256"][key] != source_hashes[key]:
                raise ValueError(f"Input changed since history coverage audit: {key}; rerun the source audit")
    train = pd.read_csv(paths["application_train.csv"])
    if train.SK_ID_CURR.isna().any() or train.SK_ID_CURR.duplicated().any():
        raise ContractError("Application customer keys must be unique and nonmissing")
    if train.TARGET.isna().any() or not train.TARGET.isin([0, 1]).all():
        raise ContractError("TARGET must be binary and nonmissing")
    raw_rows = len(train)
    lite_frame, exclusions = application_features(train.assign(IS_TRAIN=1), return_exclusions=True)
    eligible = train.set_index("SK_ID_CURR").loc[lite_frame.SK_ID_CURR]
    # All optional fields are read from the same application snapshot. Unknown inquiry
    # windows are preserved as null; no row imputation or label-informed transform.
    def numeric(source, label):
        converted = source.apply(pd.to_numeric, errors="coerce")
        malformed = source.notna() & converted.isna()
        if malformed.any().any() if isinstance(malformed, pd.DataFrame) else malformed.any():
            raise ContractError(f"Unparseable nonmissing numeric value in {label}")
        return converted

    ext = numeric(eligible[EXT_SCORES], "external score")
    if ((ext < 0) | (ext > 1)).any().any():
        raise ContractError("External score outside the observed normalized [0,1] domain")
    extra = ext.copy()
    for col in EXT_SCORES:
        extra[col.lower() + "_missing"] = ext[col].isna().astype("int8")
    enquiry_sources = [f"AMT_REQ_CREDIT_BUREAU_{x}" for x in ("HOUR", "DAY", "WEEK", "MON", "QRT", "YEAR")]
    inquiry = numeric(eligible[enquiry_sources], "bureau inquiry count")
    if (inquiry.lt(0).fillna(False)).any().any():
        raise ContractError("Negative bureau inquiry count")
    missing_pattern = inquiry.isna().nunique(axis=1)
    # Home Credit normally stores these together; flag the all-missing state. Keep
    # individual windows nullable, and report mixed missingness as a quality issue.
    extra["credit_bureau_inquiry_history_missing"] = inquiry.isna().all(axis=1).astype("int8")
    extra["credit_bureau_inquiries_1m"] = inquiry["AMT_REQ_CREDIT_BUREAU_MON"]
    extra["credit_bureau_inquiries_3m"] = inquiry["AMT_REQ_CREDIT_BUREAU_QRT"]
    extra["credit_bureau_inquiries_12m"] = inquiry["AMT_REQ_CREDIT_BUREAU_YEAR"]
    goods = numeric(eligible[["AMT_GOODS_PRICE"]], "goods price")["AMT_GOODS_PRICE"]
    credit = numeric(eligible[["AMT_CREDIT"]], "credit amount")["AMT_CREDIT"]
    if goods.isna().any() or goods.le(0).any() or credit.isna().any():
        raise ContractError("Goods price and requested credit must be observed; goods price must be positive")
    extra["loan_to_goods_price_ratio"] = credit / goods
    extra.index = eligible.index
    base = lite_frame.set_index("SK_ID_CURR").drop(columns=["IS_TRAIN", "TARGET"], errors="ignore")
    # Include the target as a distinct label, never as a feature.
    frame = base.join(extra).join(eligible[["TARGET"]]).reset_index()
    if frame.SK_ID_CURR.duplicated().any() or frame.TARGET.isna().any():
        raise ContractError("Join changed training row identity or dropped labels")
    validate_features(frame, "lite")
    if len(FEATURES) != 28 or not set(FEATURES).issubset(frame.columns):
        raise ContractError("FULL_RESEARCH_V1 feature list mismatch")
    if missing_pattern.ne(1).any():
        # Record rather than silently harmonize inconsistent null patterns.
        mixed_window_rows = int(missing_pattern.ne(1).sum())
    else:
        mixed_window_rows = 0
    frame = frame[["SK_ID_CURR"] + FEATURES + ["TARGET"]].sort_values("SK_ID_CURR").reset_index(drop=True)
    frame.to_parquet(output_dir / "full_research_v1_train.parquet", index=False)

    prior_coverage = pd.read_csv(REPO_ROOT / "ml/full_dataset_output/20261004-readiness-v1/source_coverage.csv")
    raw_coverage = dict(zip(prior_coverage.source, prior_coverage.raw_row_coverage_pct))
    metadata = json.loads((raw_dir / "adapter_manifest.json").read_text(encoding="utf-8")) if (raw_dir / "adapter_manifest.json").exists() else {}
    input_hashes = dict(source_hashes)  # Include the research-assumption manifest.
    missing_pct = frame[FEATURES].isna().mean() * 100
    inventory = []
    for col in FEATURES:
        source_missing_pct = float(missing_pct[col])
        if col == "occupation":
            source_missing_pct = float(eligible.OCCUPATION_TYPE.isna().mean() * 100)
        elif col == "housing_status":
            source_missing_pct = float(eligible.NAME_HOUSING_TYPE.isna().mean() * 100)
        if col in LITE_FEATURES:
            source = "application_train.csv"
            definition = LITE_DEFS[col]
            concerns = "Inherited, already implemented shared Lite feature; monetary period/currency retain documented RESEARCH assumptions."
            coverage = float(frame[col].notna().mean() * 100)
            recommendation = "KEEP"
        else:
            source = "application_train.csv"
            definition = APP_EXTRA_DEFS[col]
            concerns = {
                "EXT_SOURCE_1": "Underlying provider/meaning is unspecified; source cannot be collected from current user form.",
                "EXT_SOURCE_2": "Underlying provider/meaning is unspecified; source cannot be collected from current user form.",
                "EXT_SOURCE_3": "Underlying provider/meaning is unspecified; source cannot be collected from current user form.",
                "ext_source_1_missing": "Missingness can encode provider coverage/access; audit subgroup behavior.",
                "ext_source_2_missing": "Missingness can encode provider coverage/access; audit subgroup behavior.",
                "ext_source_3_missing": "Missingness can encode provider coverage/access; audit subgroup behavior.",
                "credit_bureau_inquiries_1m": "Three nonoverlapping source windows only; source values can still contain collection/definition drift.",
                "credit_bureau_inquiries_3m": "Three nonoverlapping source windows only; source values can still contain collection/definition drift.",
                "credit_bureau_inquiries_12m": "Three nonoverlapping source windows only; source values can still contain collection/definition drift.",
                "credit_bureau_inquiry_history_missing": "Missingness may reflect bureau/provider coverage rather than applicant behavior.",
                "loan_to_goods_price_ratio": "Contract quotation feature; denominator must remain positive; monetary units cancel if same currency.",
            }[col]
            coverage = float(frame[col].notna().mean() * 100)
            recommendation = "KEEP"
        inventory.append({"feature": col, "source_dataset": source, "definition": definition,
                          "missingness_pct": float(missing_pct[col]), "coverage_pct": coverage,
                          "source_value_missingness_pct": source_missing_pct,
                          "data_quality_concerns": concerns, "recommendation": recommendation,
                          "measured_row_coverage_pct": coverage})
    expected_history = {name for names in HISTORY_GROUPS.values() for name in names}
    if set(HISTORY_DEFS) != expected_history:
        raise ContractError("Candidate inventory is out of sync with existing Full history contract")
    history_source = {name: key for key, names in HISTORY_GROUPS.items() for name in names}
    for col, definition in HISTORY_DEFS.items():
        group = history_source[col]
        source = {"bureau": "bureau.csv", "bureau_balance": "bureau_balance.csv", "previous_application": "previous_application.csv",
                  "installments_payments": "installments_payments.csv", "pos_cash_balance": "POS_CASH_balance.csv",
                  "credit_card_balance": "credit_card_balance.csv"}[group]
        inventory.append({"feature": col, "source_dataset": source, "definition": definition,
                          "missingness_pct": None, "coverage_pct": None,
                          "source_value_missingness_pct": None,
                          "data_quality_concerns": "Not measured/generated: excluded by FULL_RESEARCH_V1 point-in-time or identity gate. Raw applicant source-row coverage is a proxy only, not feature coverage: %.4f%%. " % raw_coverage[group] + {
                              "bureau": "Missing DAYS_AVAILABLE; 8,418 negative debt values; missing debt amounts; 11.43% bureau-balance rows unmapped.",
                              "bureau_balance": "Missing DAYS_AVAILABLE; 3,120,184 rows (11.43%) cannot map to a bureau account.",
                              "previous_application": "Missing DAYS_AVAILABLE; decision time alone does not prove when this lender could observe a record.",
                              "installments_payments": "Missing DAYS_AVAILABLE and PAYMENT_ID; effective schedule absent; payment rows cannot safely be reconciled into obligations.",
                              "pos_cash_balance": "Missing DAYS_AVAILABLE; snapshot age alone does not prove historical availability.",
                              "credit_card_balance": "Missing DAYS_AVAILABLE; snapshot age alone does not prove historical availability; negative balance semantics require care."
                          }[group], "recommendation": "DROP", "measured_row_coverage_pct": float(raw_coverage[group])})
    inv = pd.DataFrame(inventory)
    inv.to_csv(output_dir / "feature_inventory.csv", index=False)
    inv[inv.recommendation.eq("KEEP")].to_csv(output_dir / "missingness_report.csv", index=False)
    inv[inv.recommendation.eq("DROP")].to_csv(output_dir / "excluded_history_features.csv", index=False)
    coverage_rows = [{"feature": r["feature"], "source_dataset": r["source_dataset"],
                      "measured_feature_coverage_pct": r["coverage_pct"],
                      "raw_source_coverage_proxy_pct": r["measured_row_coverage_pct"],
                      "recommendation": r["recommendation"]} for r in inventory]
    pd.DataFrame(coverage_rows).to_csv(output_dir / "coverage_report.csv", index=False)
    dist = {}
    for col in FEATURES:
        s = frame[col]
        if col in CATEGORICAL:
            dist[col] = {str(k): int(v) for k, v in s.value_counts(dropna=False).items()}
        else:
            v = s.dropna().astype(float)
            hist, edges = np.histogram(v, bins=np.unique(np.linspace(v.min(), v.max(), 21)) if v.nunique() > 1 else 1)
            dist[col] = {"missing": int(s.isna().sum()), "min": float(v.min()), "mean": float(v.mean()), "max": float(v.max()),
                         "p01": float(v.quantile(.01)), "p25": float(v.quantile(.25)), "p50": float(v.quantile(.5)),
                         "p75": float(v.quantile(.75)), "p99": float(v.quantile(.99)), "histogram_counts": hist.tolist(),
                         "histogram_edges": edges.tolist()}
    write_json(output_dir / "feature_distributions.json", dist)
    contract_feature_definitions = []
    for col in FEATURES:
        contract_feature_definitions.append({"name": col, "type": "categorical" if col in CATEGORICAL else "numeric",
                                             "source_dataset": "application_train.csv",
                                             "definition": LITE_DEFS.get(col, APP_EXTRA_DEFS.get(col)),
                                             "missing_values": "Preserved as null; imputation fitted on training folds only." if frame[col].isna().any() else "None in eligible research cohort."})
    contract = {
        "contract": CONTRACT_VERSION, "version": "full-research-v1.0.0", "scope": "RESEARCH_ONLY",
        "feature_count": len(FEATURES), "features": FEATURES, "categorical_features": CATEGORICAL,
        "feature_definitions": contract_feature_definitions,
        "target": {"column": "TARGET", "source": "application_train.csv", "meaning": "Home Credit label as supplied; fixed prediction horizon is unverified"},
        "row_key": "SK_ID_CURR", "cohort": "eligible CASH loan application_train rows only; application_test excluded",
        "input_feature_source": "Application record snapshot only. No bureau/previous/installment/POS/card aggregates enter this contract.",
        "required_raw_columns": ["SK_ID_CURR", "TARGET", "NAME_CONTRACT_TYPE", "DAYS_BIRTH", "DAYS_EMPLOYED", "AMT_INCOME_TOTAL", "AMT_CREDIT", "AMT_ANNUITY", "CNT_FAM_MEMBERS", "CNT_CHILDREN", "NAME_INCOME_TYPE", "NAME_EDUCATION_TYPE", "OCCUPATION_TYPE", "NAME_HOUSING_TYPE", "EXT_SOURCE_1", "EXT_SOURCE_2", "EXT_SOURCE_3", "AMT_REQ_CREDIT_BUREAU_HOUR", "AMT_REQ_CREDIT_BUREAU_DAY", "AMT_REQ_CREDIT_BUREAU_WEEK", "AMT_REQ_CREDIT_BUREAU_MON", "AMT_REQ_CREDIT_BUREAU_QRT", "AMT_REQ_CREDIT_BUREAU_YEAR", "AMT_GOODS_PRICE"],
        "assumptions": ["Dataset is the standard Kaggle Home Credit dataset as user asserted.",
                        "AMT_INCOME_TOTAL annual and AMT_ANNUITY monthly are research assumptions, not independently verified.",
                        "EXT_SOURCE values are accepted only as normalized application-record fields; provider identity and live availability are unknown.",
                        "Application snapshot is treated as the prediction-time record; TARGET horizon/population are not independently established."],
        "excluded_source_datasets": ["bureau.csv", "bureau_balance.csv", "previous_application.csv", "installments_payments.csv", "POS_CASH_balance.csv", "credit_card_balance.csv"],
        "preprocessing": "Raw numeric nulls preserved; fit imputation/scaling/encoding only within training folds.",
        "excluded_feature_families": ["bureau and bureau_balance aggregates (DAYS_AVAILABLE absent; bureau-balance account mapping failures)",
                                      "previous-application aggregates (availability at current application unverified)",
                                      "installment aggregates (payment event identity and complete effective schedule unresolved)",
                                      "POS and card snapshot aggregates (DAYS_AVAILABLE absent)",
                                      "application demographics and region/document flags beyond the inherited Lite contract (fairness/proxy risk; not in this research version)"],
        "release_ready": False, "model_trained": False
    }
    if CONTRACT_PATH.exists():
        committed_contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
        if committed_contract != contract:
            raise ContractError("Versioned FULL_RESEARCH_V1 contract differs from builder; review/version before rebuilding")
    else:
        write_json(CONTRACT_PATH, contract)
    write_json(output_dir / "FULL_RESEARCH_V1.json", contract)
    target_counts = {str(k): int(v) for k, v in frame.TARGET.value_counts().items()}
    result = {"contract": CONTRACT_VERSION, "status": "RESEARCH_DATASET_BUILT_MODEL_NOT_TRAINED", "training_ready": True,
              "production_ready": False, "release_ready": False, "synthetic": False,
              "source_rows": raw_rows, "eligible_rows": len(frame), "excluded_application_rows": len(exclusions),
              "feature_count": len(FEATURES), "history_features_kept": 0, "history_features_dropped": len(HISTORY_DEFS),
              "target_distribution": target_counts, "mixed_inquiry_missingness_rows": mixed_window_rows,
              "input_sha256": input_hashes, "builder_sha256": sha256(Path(__file__)),
              "feature_pipeline_sha256": {"contracts.py": sha256(ML_ROOT / "creditiq_ml/contracts.py"),
                                          "features.py": sha256(ML_ROOT / "creditiq_ml/features.py")},
              "runtime": {"python": sys.version.split()[0], "pandas": pd.__version__, "numpy": np.__version__},
              "dataset_sha256": sha256(output_dir / "full_research_v1_train.parquet"),
              "contract_sha256": sha256(output_dir / "FULL_RESEARCH_V1.json"), "model_trained": False,
              "lite_artifacts_modified": False, "existing_contracts_modified": False}
    write_json(output_dir / "build_manifest.json", result)
    return result, inv, target_counts, exclusions, missing_pct


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    a = parser.parse_args()
    try:
        result, *_ = build(a.raw_dir, a.output_dir)
    except (ContractError, ValueError, OSError, KeyError) as exc:
        parser.exit(1, f"FULL_RESEARCH_V1 build failed: {exc}\n")
    print(json.dumps(result, indent=2))
