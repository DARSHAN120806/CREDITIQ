"""Train and evaluate the isolated FULL_RESEARCH_V1_NO_EXT experiment.

This script only reads the existing FULL_RESEARCH_V1 dataset and pinned Lite
artifacts. It does not alter production contracts, models, artifacts, or APIs.
Run from ml/: python tools/full_research_v1_no_ext.py
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import shap
from sklearn.calibration import calibration_curve
from sklearn.metrics import (average_precision_score, brier_score_loss,
                             log_loss, roc_auc_score)

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from creditiq_ml import config as C  # noqa: E402
from creditiq_ml.contracts import CATEGORICAL  # noqa: E402
from creditiq_ml.preprocessing import build_preprocessor, split_columns  # noqa: E402
from creditiq_ml.train import (ProbabilityCalibrator, make_pipeline, metrics,
                               select_on_development, tune)  # noqa: E402

CONTRACT = ROOT / "research_contracts" / "FULL_RESEARCH_V1.json"
NO_EXT_CONTRACT = ROOT / "research_contracts" / "FULL_RESEARCH_V1_NO_EXT.json"
SOURCE_DATA = ROOT / "research_output" / "full_research_v1" / "20261004-delivery" / "full_research_v1_train.parquet"
LITE_RUN_ID = "20261002T140817Z-045430a7"
LITE_ARTIFACT = ROOT / "real_data_output" / "artifacts" / "lite" / "runs" / LITE_RUN_ID
OUTPUT_ROOT = ROOT / "research_output" / "full_research_v1_no_ext"
REMOVE = {
    "EXT_SOURCE_1", "EXT_SOURCE_2", "EXT_SOURCE_3",
    "ext_source_1_missing", "ext_source_2_missing", "ext_source_3_missing",
}
NEW_FEATURES = [
    "credit_bureau_inquiries_1m", "credit_bureau_inquiries_3m",
    "credit_bureau_inquiries_12m", "credit_bureau_inquiry_history_missing",
    "loan_to_goods_price_ratio",
]
BASE_LITE = [
    "age_years", "years_employed", "annual_income", "requested_amount",
    "quoted_monthly_payment", "household_size", "dependent_children",
    "employment_type", "education_level", "occupation", "housing_status",
    "employment_tenure_missing", "proposed_payment_income_ratio",
    "principal_income_ratio", "income_per_household_member",
    "employed_age_ratio", "payment_principal_ratio",
]


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def make_contract(source: dict) -> dict:
    features = [row for row in source["feature_definitions"] if row["name"] not in REMOVE]
    actual = [row["name"] for row in features]
    expected = [name for name in (row["name"] for row in source["feature_definitions"]) if name not in REMOVE]
    if actual != expected or len(actual) != source["feature_count"] - len(REMOVE):
        raise ValueError("NO_EXT contract feature selection is inconsistent")
    result = dict(source)
    result.update(contract="FULL_RESEARCH_V1_NO_EXT", feature_count=len(actual), feature_definitions=features)
    result["excluded_feature_families"] = list(source["excluded_feature_families"]) + [
        "EXT_SOURCE_1/2/3 and missingness flags omitted from this contract; no other FULL_RESEARCH_V1 features changed"
    ]
    result["assumptions"] = [
        item for item in source["assumptions"]
        if "EXT_SOURCE values" not in item
    ] + ["All six EXT_SOURCE score and missingness features are excluded by design."]
    return result


def calibration_metrics(y, p):
    observed, predicted = calibration_curve(y, p, n_bins=10, strategy="quantile")
    bins = [{"mean_predicted_probability": float(x), "observed_default_rate": float(z)}
            for x, z in zip(predicted, observed)]
    return {"roc_auc": float(roc_auc_score(y, p)),
            "average_precision": float(average_precision_score(y, p)),
            "brier_score": float(brier_score_loss(y, p)),
            "log_loss": float(log_loss(y, np.clip(p, 1e-7, 1 - 1e-7))),
            "calibration_bins": bins}


def fit_probabilities(features, parts, params, method):
    dev, cal, evaluate = (parts[k] for k in ("development", "calibration", "policy"))
    X = dev[features]
    num, cat = split_columns(X)
    model = make_pipeline("lightgbm", params, num, cat, 1.0).fit(X, dev[C.TARGET].astype(int))
    calibrator = ProbabilityCalibrator(method).fit(
        model.predict_proba(cal[features])[:, 1], cal[C.TARGET].astype(int))
    probability = calibrator.predict(model.predict_proba(evaluate[features])[:, 1])
    return model, calibrator, probability


def main() -> None:
    source_contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    contract = make_contract(source_contract)
    features = [item["name"] for item in contract["feature_definitions"]]
    if len(features) != 22 or set(features) & REMOVE or set(features) != (set(
            item["name"] for item in source_contract["feature_definitions"]) - REMOVE):
        raise ValueError("Expected exactly the original 28 features minus the six named EXT_SOURCE features")

    full = pd.read_parquet(SOURCE_DATA)
    if set(features + [C.ID_COL, C.TARGET]) - set(full.columns):
        raise ValueError("Research dataset does not satisfy the NO_EXT contract")
    lite_meta = json.loads((LITE_ARTIFACT / "metadata.json").read_text(encoding="utf-8"))
    saved_splits = json.loads((LITE_ARTIFACT / "splits.json").read_text(encoding="utf-8"))
    lite_predictions = pd.read_parquet(LITE_ARTIFACT / "test_predictions.parquet")
    if full[C.ID_COL].duplicated().any():
        raise ValueError("Research dataset applicant IDs must be unique")
    full = full.set_index(C.ID_COL)
    if set(saved_splits) != {"development", "calibration", "policy", "test"}:
        raise ValueError("Pinned Lite split manifest is incomplete")
    ids = {name: [int(value) for value in rows] for name, rows in saved_splits.items()}
    if set(map(int, full.index)) != set(map(int, sum(ids.values(), []))):
        raise ValueError("NO_EXT and Lite eligible cohorts differ; paired evaluation is not valid")
    parts = {name: full.loc[rows] for name, rows in ids.items()}
    test_ids = set(ids["test"])
    if lite_predictions.customer_id.duplicated().any():
        raise ValueError("Pinned Lite test prediction IDs must be unique")
    lite_test = lite_predictions.set_index("customer_id")
    if set(map(int, lite_test.index)) != test_ids:
        raise ValueError("Pinned Lite test predictions do not match the shared final test cohort")
    if not np.array_equal(parts["test"][C.TARGET].astype(int).sort_index().to_numpy(),
                          lite_test.loc[sorted(test_ids), "target"].astype(int).to_numpy()):
        raise ValueError("Lite prediction labels differ from the research dataset labels")

    dev = parts["development"]
    X, y = dev[features], dev[C.TARGET].astype(int)
    n_trials = int(lite_meta.get("search_budget", {}).get("optuna_trials", 5))
    tune_rows = int(lite_meta.get("search_budget", {}).get("tune_rows", C.TUNE_ROWS))
    # Reuse the existing nested development selection and Optuna LightGBM path.
    selection, folds, _ = select_on_development(X, y, ["lightgbm"], n_trials, tune_rows)
    chosen = selection.iloc[0]
    method = str(chosen.Calibration)
    num, cat = split_columns(X)
    params, cv_auc = tune("lightgbm", X, y, num, cat, 1.0, n_trials)
    development_model = make_pipeline("lightgbm", params, num, cat, 1.0).fit(X, y)
    cal_part, test = parts["calibration"], parts["test"]
    calibrator = ProbabilityCalibrator(method).fit(
        development_model.predict_proba(cal_part[features])[:, 1], cal_part[C.TARGET].astype(int))
    raw_test = development_model.predict_proba(test[features])[:, 1]
    full_test_probability = calibrator.predict(raw_test)
    lite_test = lite_test.loc[test.index]
    lite_probability = lite_test["pd"].to_numpy(dtype=float)
    y_test = test[C.TARGET].astype(int).to_numpy()

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output = OUTPUT_ROOT / run_id
    output.mkdir(parents=True, exist_ok=False)
    if NO_EXT_CONTRACT.exists() and json.loads(NO_EXT_CONTRACT.read_text(encoding="utf-8")) != contract:
        raise ValueError("Versioned NO_EXT contract differs from the reproducible derived contract")
    write_json(NO_EXT_CONTRACT, contract)
    write_json(output / "FULL_RESEARCH_V1_NO_EXT.json", contract)
    full[features + [C.TARGET]].reset_index().to_parquet(output / "full_research_v1_no_ext_train.parquet", index=False)
    selection.to_csv(output / "development_model_selection.csv", index=False)
    folds.to_csv(output / "development_selection_folds.csv", index=False)

    comparison = {
        "evaluation": "same pinned, untouched Lite final-test cohort; paired applicant-level comparison",
        "test_rows": len(test), "test_default_rate": float(y_test.mean()),
        "Lite": calibration_metrics(y_test, lite_probability),
        "FULL_RESEARCH_V1_NO_EXT": calibration_metrics(y_test, full_test_probability),
        "calibration_method_no_ext": method,
        "differences_no_ext_minus_lite": {
            key: float(calibration_metrics(y_test, full_test_probability)[key] - calibration_metrics(y_test, lite_probability)[key])
            for key in ("roc_auc", "average_precision", "brier_score", "log_loss")
        },
        "interpretation": "Descriptive research comparison. AUC/AP higher is better; Brier/log-loss lower is better. The existing Lite artifact is unchanged."
    }
    write_json(output / "model_comparison.json", comparison)
    pd.DataFrame([
        {"model": name, **{k: v for k, v in values.items() if k != "calibration_bins"}}
        for name, values in (("Lite", comparison["Lite"]), ("FULL_RESEARCH_V1_NO_EXT", comparison["FULL_RESEARCH_V1_NO_EXT"]))
    ]).to_csv(output / "model_comparison.csv", index=False)
    write_json(output / "calibration_results.json", {
        "cohort": "untouched final test", "Lite": comparison["Lite"]["calibration_bins"],
        "FULL_RESEARCH_V1_NO_EXT": comparison["FULL_RESEARCH_V1_NO_EXT"]["calibration_bins"]})
    plt.figure(figsize=(7, 6))
    for label, vals in (("Lite", comparison["Lite"]), ("FULL_RESEARCH_V1_NO_EXT", comparison["FULL_RESEARCH_V1_NO_EXT"])):
        bins = vals["calibration_bins"]
        plt.plot([b["mean_predicted_probability"] for b in bins],
                 [b["observed_default_rate"] for b in bins], marker="o", label=label)
    plt.plot([0, 1], [0, 1], "--", color="gray", label="Ideal")
    plt.xlabel("Mean predicted default probability"); plt.ylabel("Observed default rate")
    plt.title("Paired final-test calibration"); plt.legend(); plt.tight_layout()
    plt.savefig(output / "calibration_comparison.png", dpi=150); plt.close()
    pd.DataFrame({"SK_ID_CURR": test.index, "TARGET": y_test, "lite_probability": lite_probability,
                  "no_ext_probability": full_test_probability}).to_parquet(output / "paired_test_predictions.parquet", index=False)

    # Ablations are diagnostic on the reserved policy cohort, not the final test.
    ablations = {"FULL_RESEARCH_V1_NO_EXT": features,
                 "Lite feature subset (17)": [name for name in features if name in BASE_LITE],
                 "Without inquiry features": [name for name in features if name not in NEW_FEATURES[:4]],
                 "Without loan-to-goods ratio": [name for name in features if name != NEW_FEATURES[4]]}
    policy = parts["policy"]
    ablation_rows = []
    for label, selected in ablations.items():
        if not selected:
            continue
        pipe, cal, _ = fit_probabilities(selected, parts, params, method)
        raw_policy = pipe.predict_proba(policy[selected])[:, 1]
        policy_calibrated = cal.predict(raw_policy)
        row = {"variant": label, "feature_count": len(selected),
               "roc_auc": float(roc_auc_score(policy[C.TARGET], policy_calibrated)),
               "average_precision": float(average_precision_score(policy[C.TARGET], policy_calibrated)),
               "brier_score": float(brier_score_loss(policy[C.TARGET], policy_calibrated)),
               "evaluation_cohort": "reserved policy partition; diagnostic only"}
        ablation_rows.append(row)
    pd.DataFrame(ablation_rows).to_csv(output / "feature_ablation_summary.csv", index=False)

    # Explain uncalibrated tree output over a deterministic final-test sample.
    transformed = development_model.named_steps["prep"].transform(test[features].sample(
        min(1000, len(test)), random_state=C.SEED))
    clf = development_model.named_steps["clf"]
    explainer = shap.TreeExplainer(clf)
    shap_values = explainer.shap_values(transformed)
    if isinstance(shap_values, list):
        shap_values = shap_values[-1]
    shap_values = np.asarray(shap_values)
    if shap_values.ndim == 3:
        shap_values = shap_values[:, :, -1]
    names = list(development_model.named_steps["prep"].get_feature_names_out())
    if shap_values.shape[1] != len(names):
        raise ValueError("SHAP dimensions do not match preprocessed feature names")
    importance = pd.DataFrame({"feature": names, "mean_abs_shap_raw_margin": np.abs(shap_values).mean(axis=0)})
    importance = importance.sort_values("mean_abs_shap_raw_margin", ascending=False)
    importance.to_csv(output / "shap_feature_importance.csv", index=False)
    importance.head(20).to_csv(output / "top_20_features.csv", index=False)
    plt.figure(figsize=(9, 8))
    shown = importance.head(20).sort_values("mean_abs_shap_raw_margin")
    plt.barh(shown.feature, shown.mean_abs_shap_raw_margin, color="#0F766E")
    plt.xlabel("Mean absolute SHAP value (raw margin)"); plt.title("FULL_RESEARCH_V1_NO_EXT top features")
    plt.tight_layout(); plt.savefig(output / "shap_top_20.png", dpi=150); plt.close()

    joblib.dump({"pipeline": development_model, "calibrator": calibrator,
                 "feature_columns": features, "calibration_method": method}, output / "lightgbm_model.joblib")
    write_json(output / "metadata.json", {
        "run_id": run_id, "contract": contract["contract"], "feature_count": len(features),
        "feature_columns": features, "removed_features": sorted(REMOVE), "best_model": "lightgbm",
        "params": params, "development_cv_auc": float(cv_auc), "selection": selection.to_dict("records"),
        "calibration_method": method, "split_sizes": {k: len(v) for k, v in ids.items()},
        "split_source": f"pinned Lite run {LITE_RUN_ID}", "test_metrics": comparison,
        "eligibility": "same 278,220 eligible application_train CASH rows as pinned Lite cohort; application_test excluded",
        "mode": "RESEARCH_ONLY", "release_ready": False,
        "shap_interpretation": "Tree SHAP explains the LightGBM raw margin before probability calibration; it is not a causal explanation.",
        "ablation_cohort": "policy partition, diagnostic only; final test remains reserved for the paired headline comparison"})
    write_json(OUTPUT_ROOT / "latest.json", {"run_id": run_id})
    print(json.dumps({"run_id": run_id, "output": str(output), "features": len(features),
                      "test_metrics": comparison, "ablation": ablation_rows}, indent=2))


if __name__ == "__main__":
    main()
