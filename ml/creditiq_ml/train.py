"""Model training: split -> tune (Grid / Optuna) -> fit -> calibrate -> evaluate -> persist."""
from __future__ import annotations
import json
import logging
import time
import platform
import importlib.metadata
from uuid import uuid4
from datetime import datetime, timezone
import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import optuna
import pandas as pd
from lightgbm import LGBMClassifier
from sklearn.base import clone
from sklearn.calibration import calibration_curve
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (accuracy_score, average_precision_score, brier_score_loss, confusion_matrix,
                             f1_score, log_loss, precision_recall_curve, precision_score, recall_score,
                             roc_auc_score, roc_curve)
from sklearn.model_selection import GridSearchCV, StratifiedKFold, cross_val_score, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import RandomForestClassifier
from sklearn.tree import DecisionTreeClassifier
from xgboost import XGBClassifier

from . import config as C
from .features import build_feature_table
from .model_wrapper import CreditRiskModel
from .preprocessing import build_preprocessor, split_columns
from .risk import risk_level, risk_score
from .risk import DecisionPolicy, risk_band
from .contracts import ContractError, feature_names, TARGET_VERSION, CATEGORICAL
from .provenance import input_manifest, source_manifest, write_json, sha256, fingerprint


class FoldBalancedXGBClassifier(XGBClassifier):
    """Estimate imbalance from the fitting fold, never outer/validation labels."""
    def fit(self, X, y, **kwargs):
        y = np.asarray(y)
        self.set_params(scale_pos_weight=float((y == 0).sum() / max(1, (y == 1).sum())))
        return super().fit(X, y, **kwargs)

log = logging.getLogger(__name__)
optuna.logging.set_verbosity(optuna.logging.WARNING)


# ------------------------------------------------------------------ model factory
def make_estimator(name: str, params: dict, pos_weight: float):
    s = C.SEED
    if name == "logistic_regression":
        return LogisticRegression(max_iter=500, class_weight="balanced", random_state=s, **params)
    if name == "decision_tree":
        return DecisionTreeClassifier(class_weight="balanced", random_state=s, **params)
    if name == "random_forest":
        return RandomForestClassifier(n_estimators=300, class_weight="balanced_subsample", n_jobs=C.N_JOBS,
                                      random_state=s, **params)
    if name == "xgboost":
        return FoldBalancedXGBClassifier(tree_method="hist", eval_metric="auc",
                             n_jobs=C.N_JOBS, random_state=s, **params)
    if name == "lightgbm":
        return LGBMClassifier(is_unbalance=True, subsample_freq=1, n_jobs=C.N_JOBS, random_state=s,
                              verbose=-1, **params)
    raise ValueError(name)


def make_pipeline(name, params, num_cols, cat_cols, pos_weight) -> Pipeline:
    steps = [("prep", build_preprocessor(num_cols, cat_cols))]
    if name == "logistic_regression":
        steps.append(("scale", StandardScaler().set_output(transform="pandas")))
    steps.append(("clf", make_estimator(name, params, pos_weight)))
    return Pipeline(steps)


GRIDS = {
    "logistic_regression": {"clf__C": [0.01, 0.05, 0.2, 1.0]},
    "decision_tree": {"clf__max_depth": [4, 6, 8], "clf__min_samples_leaf": [50, 200]},
    "random_forest": {"clf__max_depth": [8, 12], "clf__min_samples_leaf": [50, 100], "clf__max_features": ["sqrt", 0.3]},
}


def optuna_space(name, t):
    if name == "xgboost":
        return dict(n_estimators=t.suggest_int("n_estimators", 200, 600),
                    learning_rate=t.suggest_float("learning_rate", 0.02, 0.15, log=True),
                    max_depth=t.suggest_int("max_depth", 3, 8),
                    min_child_weight=t.suggest_int("min_child_weight", 1, 50),
                    subsample=t.suggest_float("subsample", 0.6, 1.0),
                    colsample_bytree=t.suggest_float("colsample_bytree", 0.4, 1.0),
                    reg_lambda=t.suggest_float("reg_lambda", 1e-2, 50, log=True),
                    reg_alpha=t.suggest_float("reg_alpha", 1e-3, 10, log=True))
    return dict(n_estimators=t.suggest_int("n_estimators", 200, 700),
                learning_rate=t.suggest_float("learning_rate", 0.02, 0.15, log=True),
                num_leaves=t.suggest_int("num_leaves", 15, 127),
                max_depth=t.suggest_int("max_depth", 3, 12),
                min_child_samples=t.suggest_int("min_child_samples", 20, 200),
                subsample=t.suggest_float("subsample", 0.6, 1.0),
                colsample_bytree=t.suggest_float("colsample_bytree", 0.4, 1.0),
                reg_lambda=t.suggest_float("reg_lambda", 1e-2, 50, log=True),
                reg_alpha=t.suggest_float("reg_alpha", 1e-3, 10, log=True))


def tune(name, Xs, ys, num_cols, cat_cols, pos_weight, n_trials):
    cv = StratifiedKFold(3, shuffle=True, random_state=C.SEED)
    if name in GRIDS:
        gs = GridSearchCV(make_pipeline(name, {}, num_cols, cat_cols, pos_weight), GRIDS[name],
                          scoring="roc_auc", cv=cv, n_jobs=1, refit=False)
        gs.fit(Xs, ys)
        return {k.replace("clf__", ""): v for k, v in gs.best_params_.items()}, float(gs.best_score_)

    def objective(trial):
        pipe = make_pipeline(name, optuna_space(name, trial), num_cols, cat_cols, pos_weight)
        return cross_val_score(pipe, Xs, ys, cv=cv, scoring="roc_auc", n_jobs=1).mean()

    study = optuna.create_study(direction="maximize", sampler=optuna.samplers.TPESampler(seed=C.SEED))
    study.optimize(objective, n_trials=n_trials)
    return study.best_params, float(study.best_value)


# ------------------------------------------------------------------ metrics
def ks_stat(y, p):
    fpr, tpr, _ = roc_curve(y, p)
    return float(np.max(tpr - fpr))


def metrics(y, p, thr):
    if set(np.unique(y)) != {0, 1}:
        raise ContractError("Evaluation requires both target classes")
    yhat = (p >= thr).astype(int)
    auc = roc_auc_score(y, p)
    return {"Accuracy": accuracy_score(y, yhat), "Precision": precision_score(y, yhat, zero_division=0),
            "Recall": recall_score(y, yhat, zero_division=0), "F1": f1_score(y, yhat, zero_division=0), "ROC_AUC": auc,
            "Gini": 2 * auc - 1, "KS": ks_stat(y, p), "AveragePrecision": average_precision_score(y, p),
            "Brier": brier_score_loss(y, p), "LogLoss": log_loss(y, np.clip(p, 1e-6, 1 - 1e-6)),
            "Threshold": thr}



class ProbabilityCalibrator:
    """Unweighted calibration on natural-prevalence, disjoint data."""
    def __init__(self, method):
        if method not in ("sigmoid", "isotonic"):
            raise ValueError(method)
        self.method = method

    @staticmethod
    def _logit(p):
        p = np.clip(np.asarray(p), 1e-7, 1 - 1e-7)
        return np.log(p / (1 - p)).reshape(-1, 1)

    def fit(self, p, y):
        if set(np.unique(y)) != {0, 1}:
            raise ContractError("Calibration requires both classes")
        self.estimator = (IsotonicRegression(out_of_bounds="clip", y_min=0, y_max=1)
                          if self.method == "isotonic" else LogisticRegression(C=1e6, max_iter=1000))
        self.estimator.fit(p if self.method == "isotonic" else self._logit(p), y)
        return self

    def predict(self, p):
        if self.method == "isotonic":
            return self.estimator.predict(p)
        return self.estimator.predict_proba(self._logit(p))[:, 1]


def select_features(df, feature_set):
    cols = feature_names(feature_set)
    if set(cols) - set(df.columns):
        raise ContractError("Missing contract features")
    return cols


def split_cohorts(df):
    """Input must be unique, labeled, sorted customer rows. No feature-dependent splits."""
    if df[C.ID_COL].isna().any() or df[C.ID_COL].duplicated().any():
        raise ContractError("Customer identities must be unique")
    if df[C.TARGET].isna().any() or not df[C.TARGET].isin([0, 1]).all():
        raise ContractError("TARGET must contain only 0 and 1")
    if df[C.TARGET].value_counts().min() < 20 or df[C.TARGET].nunique() != 2:
        raise ContractError("Need at least 20 members of each class for disjoint cohorts")
    # Integer sizes avoid floating-point ceil creating a 61-row "10%" cohort of 600.
    n = len(df)
    remainder, test = train_test_split(df, test_size=round(n * C.TEST_SIZE), stratify=df[C.TARGET], random_state=C.SEED)
    remainder, policy = train_test_split(remainder, test_size=round(n * C.POLICY_SIZE), stratify=remainder[C.TARGET], random_state=C.SEED)
    development, calibration = train_test_split(remainder, test_size=round(n * C.CALIBRATION_SIZE), stratify=remainder[C.TARGET], random_state=C.SEED)
    parts = {"development": development, "calibration": calibration, "policy": policy, "test": test}
    if any(part[C.TARGET].nunique() != 2 for part in parts.values()):
        raise ContractError("Both classes required in each cohort")
    return {name: part[C.ID_COL].astype(int).tolist() for name, part in parts.items()}


def _tune_subset(X, y, limit):
    if len(X) <= limit:
        return X, y
    indices, _ = train_test_split(np.arange(len(X)), train_size=limit, stratify=y, random_state=C.SEED)
    return X.iloc[indices], y.iloc[indices]


def select_on_development(X, y, models, trials, tune_rows):
    """Nested selection: outer assessment never fits either model or calibrator."""
    num, cat = split_columns(X)
    records, lineage = [], []
    outer = StratifiedKFold(3, shuffle=True, random_state=C.SEED)
    for fold, (fit_indices, assess_indices) in enumerate(outer.split(X, y)):
        base_indices, cal_indices = train_test_split(fit_indices, test_size=.20, stratify=y.iloc[fit_indices], random_state=C.SEED)
        lineage.append({"fold": fold, "base": X.index[base_indices].tolist(),
                        "calibration": X.index[cal_indices].tolist(), "assessment": X.index[assess_indices].tolist()})
        for name in models:
            log.info("Development fold %d/3: tuning and evaluating %s", fold + 1, name)
            xs, ys = _tune_subset(X.iloc[base_indices], y.iloc[base_indices], tune_rows)
            params, inner_auc = tune(name, xs, ys, num, cat, 1.0, trials)
            pipe = make_pipeline(name, params, num, cat, 1.0).fit(X.iloc[base_indices], y.iloc[base_indices])
            cal_raw = pipe.predict_proba(X.iloc[cal_indices])[:, 1]
            assessment_raw = pipe.predict_proba(X.iloc[assess_indices])[:, 1]
            for method in ("sigmoid", "isotonic"):
                cal = ProbabilityCalibrator(method).fit(cal_raw, y.iloc[cal_indices])
                p = cal.predict(assessment_raw)
                records.append({"Model": name, "Calibration": method, "Fold": fold,
                                "Brier": brier_score_loss(y.iloc[assess_indices], p),
                                "ROC_AUC": roc_auc_score(y.iloc[assess_indices], p),
                                "AveragePrecision": average_precision_score(y.iloc[assess_indices], p),
                                "Inner_CV_AUC": inner_auc})
            log.info("Development fold %d/3: completed %s", fold + 1, name)
    raw = pd.DataFrame(records)
    comparison = raw.groupby(["Model", "Calibration"])[["Brier", "ROC_AUC", "AveragePrecision", "Inner_CV_AUC"]].mean().reset_index()
    comparison = comparison.sort_values(["Brier", "ROC_AUC", "Model", "Calibration"], ascending=[True, False, True, True])
    return comparison, raw, lineage


def policy_diagnostics(y, p):
    """Independent descriptive evidence, NOT an automatic business-policy optimizer."""
    rows = []
    for a, r in ((.03, .10), (.05, .15), (.07, .20)):
        for label, mask in (("approval_candidate", p < a), ("review", (p >= a) & (p < r)), ("rejection_candidate", p >= r)):
            n = int(mask.sum())
            rows.append({"approve_below": a, "reject_at": r, "group": label, "count": n,
                         "share": n / len(p), "observed_target_rate": float(np.asarray(y)[mask].mean()) if n else None})
    return rows


def _bootstrap(y, p, iterations=200):
    rng = np.random.RandomState(C.SEED)
    samples = []
    y = np.asarray(y)
    for _ in range(iterations):
        indices = rng.randint(0, len(y), len(y))
        if len(np.unique(y[indices])) == 2:
            samples.append([roc_auc_score(y[indices], p[indices]), average_precision_score(y[indices], p[indices]),
                            brier_score_loss(y[indices], p[indices])])
    return {name: np.quantile(np.asarray(samples)[:, i], [.025, .975]).tolist()
            for i, name in enumerate(("ROC_AUC", "AveragePrecision", "Brier"))}


def train_all(feature_set="lite", n_trials=25, models=None, max_rows=None, tune_rows=C.TUNE_ROWS, use_cache=True):
    if n_trials < 1 or tune_rows < 20 or (max_rows is not None and max_rows < 100):
        raise ContractError("Positive trials, tune_rows>=20 and max_rows>=100 required")
    models = models or C.MODEL_NAMES
    if not models or set(models) - set(C.MODEL_NAMES):
        raise ContractError("Unknown model selection")
    adapter = source_manifest(feature_set)
    df = build_feature_table(use_cache=use_cache, feature_set=feature_set)
    inputs = input_manifest(feature_set)
    feature_report = json.loads((C.PROCESSED_DIR / f"features_{feature_set}_{fingerprint(inputs)[:16]}.json").read_text())
    # Use the Lite eligible universe for identical variant partition identities.
    universe = build_feature_table(use_cache=use_cache, feature_set="lite")
    universe = universe[universe.IS_TRAIN.eq(1)].sort_values(C.ID_COL)
    if max_rows and len(universe) > max_rows:
        universe, _ = train_test_split(universe, train_size=max_rows, stratify=universe[C.TARGET], random_state=C.SEED)
        universe = universe.sort_values(C.ID_COL)
    split_ids = split_cohorts(universe)
    df = df[df.IS_TRAIN.eq(1)].set_index(C.ID_COL)
    if not set(universe[C.ID_COL]).issubset(df.index):
        raise ContractError("Full eligibility differs; reconcile shared split manifest before training")
    parts = {name: df.loc[ids] for name, ids in split_ids.items()}
    feats = select_features(df, feature_set)
    X, y = parts["development"][feats], parts["development"][C.TARGET].astype(int)
    if y.value_counts().min() < 12:
        raise ContractError("Development cohort too small for nested model/calibrator selection")
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex[:8]
    art = C.ARTIFACTS_DIR / feature_set / "runs" / run_id
    rep = C.REPORTS_DIR / "training" / feature_set / run_id
    art.mkdir(parents=True, exist_ok=False); rep.mkdir(parents=True, exist_ok=False)
    write_json(art / "splits.json", split_ids)
    comparison, fold_results, nested_ids = select_on_development(X, y, models, n_trials, tune_rows)
    comparison.to_csv(rep / "model_comparison.csv", index=False)
    fold_results.to_csv(rep / "development_folds.csv", index=False)
    write_json(art / "development_folds.json", nested_ids)
    winner = comparison.iloc[0]
    name, method = str(winner.Model), str(winner.Calibration)
    log.info("Frozen development choice: %s / %s; final development refit starts", name, method)
    num, cat = split_columns(X)
    xs, ys = _tune_subset(X, y, tune_rows)
    params, cv_auc = tune(name, xs, ys, num, cat, 1.0, n_trials)
    pipe = make_pipeline(name, params, num, cat, 1.0).fit(X, y)
    cal_part = parts["calibration"]
    cal = ProbabilityCalibrator(method).fit(pipe.predict_proba(cal_part[feats])[:, 1], cal_part[C.TARGET].astype(int))
    meta = {"run_id": run_id, "feature_set": feature_set, "schema_version": f"{feature_set}-v1",
            "mode": adapter.get("mode", "RESEARCH"),
            "research_assumptions": adapter.get("research_assumptions", {}),
            "search_budget": {"optuna_trials": n_trials, "tune_rows": tune_rows,
                              "models": list(models), "max_rows": max_rows},
            "target_definition_version": TARGET_VERSION, "currency": adapter["currency"],
            "calibration_method": method, "positive_class": 1, "release_ready": False,
            "release_status": "RESEARCH_ONLY", "synthetic": bool(adapter.get("synthetic", False)),
            "observed_categories": {c: sorted(X[c].unique().tolist()) for c in cat},
            "numeric_support": {c: [float(X[c].min()), float(X[c].max())] for c in num if X[c].notna().any()},
            "tenure_missing_observed": bool(X.years_employed.isna().any())}
    model = CreditRiskModel(name, pipe, cal, feats, cat, meta=meta)
    # Frozen-reference predictions from calibration, never final-test data.
    model.reference_probabilities = np.sort(model.predict_proba(cal_part[feats]))
    policy_part = parts["policy"]
    policy_p = model.predict_proba(policy_part[feats])
    write_json(rep / "policy_validation.json", {"status": "NOT_APPROVED_FOR_LIVE", "diagnostics": policy_diagnostics(policy_part[C.TARGET], policy_p)})
    write_json(art / "policy.json", {"version": "sandbox-v1", "mode": "SANDBOX", "approve_below": .05,
                                   "reject_at": .15, "production_thresholds": None})
    # Model/method/params and sandbox policy are now frozen. Only this champion sees test.
    test = parts["test"]
    log.info("Evaluating frozen champion on %d final-test rows", len(test))
    p = model.predict_proba(test[feats])
    test_metrics = metrics(test[C.TARGET].astype(int), p, .15)
    baseline = np.repeat(float(y.mean()), len(test))
    test_report = {"metrics": test_metrics, "bootstrap_95pct": _bootstrap(test[C.TARGET], p),
                   "baseline": {"AveragePrecision": float(test[C.TARGET].mean()), "Brier": brier_score_loss(test[C.TARGET], baseline),
                                "Accuracy_always_zero": float(1 - test[C.TARGET].mean())},
                   "threshold_purpose": "sandbox diagnostic only, not approved lending policy"}
    write_json(rep / "test_metrics.json", test_report)
    band_rows = pd.DataFrame({"band": [risk_band(v) for v in p], "target": test[C.TARGET].to_numpy(), "pd": p})
    band_rows.groupby("band").agg(count=("target", "size"), observed_rate=("target", "mean"), mean_pd=("pd", "mean")).to_csv(rep / "risk_bands.csv")
    # Keep explanatory reference and segment discovery wholly within development.
    X.sample(min(200, len(X)), random_state=C.SEED).to_parquet(art / "explanation_background.parquet", index=False)
    X.head(min(1500, len(X))).to_parquet(art / "explanation_sample.parquet", index=False)
    parts["development"][[C.TARGET] + feats].to_parquet(art / "development.parquet")
    parts["policy"][[C.TARGET] + feats].to_parquet(art / "policy_validation.parquet")
    pd.DataFrame({"customer_id": test.index, "target": test[C.TARGET].to_numpy(), "pd": p}).to_parquet(art / "test_predictions.parquet", index=False)
    joblib.dump(model, art / "best_model.joblib")
    versions = {package: importlib.metadata.version(package) for package in
                ("numpy", "pandas", "scikit-learn", "scipy", "joblib", "pyarrow", "matplotlib", "shap", "optuna", "lightgbm", "xgboost")}
    meta.update({"best_model": name, "params": params, "development_cv_auc": float(cv_auc),
                 "feature_columns": feats, "categorical_columns": cat, "numeric_columns": num,
                 "n_features_in": len(feats), "transformed_features": list(pipe[:-1].get_feature_names_out()),
                 "input_manifest": inputs, "adapter_evidence": adapter,
                 "feature_quality": {"eligible_rows": feature_report["eligible_rows"],
                                     "excluded_rows": len(feature_report["excluded_rows"]),
                                     "exclusion_reasons": pd.Series([r["reason"] for r in feature_report["excluded_rows"]]).value_counts().astype(int).to_dict(),
                                     "missing_counts": feature_report["quality_missing_counts"]},
                 "split_sizes": {k: len(v) for k, v in split_ids.items()}, "selection": "nested development Brier then ROC_AUC",
                 "runtime": {"python": platform.python_version(), "packages": versions},
                 "test_metrics": test_report, "policy": "sandbox-v1",
                 "unresolved_release_gates": ["target/horizon and population validation", "independent policy approval", "real-data cohort acceptance"],
                 "reference_cohort": "calibration", "trained_at": datetime.now(timezone.utc).isoformat()})
    # Save model again with complete immutable metadata (checksum lives outside pickle).
    joblib.dump(model, art / "best_model.joblib")
    meta_out = dict(meta)
    meta_out["artifact_sha256"] = {path.name: sha256(path) for path in art.iterdir() if path.is_file()}
    _plot_champion(test[C.TARGET], p, rep)
    write_json(art / "metadata.json", meta_out)
    write_json(C.ARTIFACTS_DIR / feature_set / "latest.json", {"run_id": run_id})
    log.info("Research champion %s/%s -> %s", name, method, art)
    print(comparison.to_string(index=False))
    return comparison


def _plot_champion(y, p, rep):
    fpr, tpr, _ = roc_curve(y, p)
    plt.figure(); plt.plot(fpr, tpr); plt.xlabel("FPR"); plt.ylabel("TPR")
    plt.title("Frozen champion ROC (final test)"); plt.savefig(rep / "roc_curves.png"); plt.close()
    precision, recall, _ = precision_recall_curve(y, p)
    plt.figure(); plt.plot(recall, precision); plt.xlabel("Recall"); plt.ylabel("Precision")
    plt.savefig(rep / "pr_curves.png"); plt.close()
    observed, predicted = calibration_curve(y, p, n_bins=10, strategy="quantile")
    plt.figure(); plt.plot(predicted, observed, "o-"); plt.plot([0, 1], [0, 1], "--")
    plt.xlabel("Calibrated PD"); plt.ylabel("Observed TARGET=1")
    plt.savefig(rep / "calibration.png"); plt.close()

