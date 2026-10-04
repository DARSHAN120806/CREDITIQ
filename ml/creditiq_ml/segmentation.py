"""Development-only, descriptive segmentation with serialized preprocessing and k selection."""
from __future__ import annotations
import joblib
import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.cluster import KMeans
from sklearn.impute import SimpleImputer
from sklearn.metrics import silhouette_score, adjusted_rand_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from . import config as C
from .contracts import ContractError
from .preprocessing import Winsorizer
from .provenance import load_model, write_json, sha256

SEG_FEATURES = ["age_years", "annual_income", "requested_amount", "proposed_payment_income_ratio",
                "years_employed", "bureau_active_count", "installment_late_rate",
                "card_historical_mean_utilization", "previous_refusal_rate"]


class LogAmounts(BaseEstimator, TransformerMixin):
    def fit(self, X, y=None):
        self.feature_names_in_ = np.array(X.columns, dtype=object)
        return self

    def transform(self, X):
        X = X.copy()
        for col in ("annual_income", "requested_amount"):
            if (X[col] <= 0).any():
                raise ContractError("Segmentation amounts must be positive")
            X[col] = np.log1p(X[col])
        return X

    def get_feature_names_out(self, input_features=None):
        return self.feature_names_in_


def segment_preprocessor():
    return Pipeline([("log", LogAmounts()), ("clip", Winsorizer()),
                     ("impute", SimpleImputer(strategy="median", keep_empty_features=True).set_output(transform="pandas")),
                     ("scale", StandardScaler().set_output(transform="pandas"))])


def fit_segmenter(development, sample=5000):
    if set(SEG_FEATURES) - set(development.columns):
        raise ContractError("Full history required for segmentation")
    if len(development) < 20:
        raise ContractError("At least 20 discovery observations required")
    prep = segment_preprocessor().fit(development[SEG_FEATURES])
    Z = prep.transform(development[SEG_FEATURES])
    discovery = Z.sample(min(sample, len(Z)), random_state=C.SEED)
    max_k = min(7, len(discovery) - 1, len(discovery.drop_duplicates()) - 1)
    rows = []
    for k in range(2, max_k + 1):
        repeats = [KMeans(k, n_init=10, random_state=seed).fit(discovery) for seed in (42, 43, 44)]
        labels = repeats[0].labels_
        if len(np.unique(labels)) != k:
            continue
        minimum_share = float(np.bincount(labels).min() / len(labels))
        stability = float(np.mean([adjusted_rand_score(labels, m.labels_) for m in repeats[1:]]))
        silhouette = float(silhouette_score(discovery, labels, sample_size=min(1000, len(discovery)), random_state=C.SEED))
        rows.append({"k": k, "silhouette": silhouette, "stability_ARI": stability,
                     "minimum_share": minimum_share, "inertia": float(repeats[0].inertia_)})
    eligible = [r for r in rows if r["minimum_share"] >= .01 and r["stability_ARI"] >= .80]
    if not eligible:
        raise ContractError("No stable nontrivial segmentation; do not force risk labels")
    chosen = max(eligible, key=lambda r: (r["silhouette"], -r["k"]))
    model = KMeans(chosen["k"], n_init=10, random_state=C.SEED).fit(Z)
    pipeline = Pipeline([("prep", prep), ("kmeans", model)])
    return pipeline, rows


def run_segmentation(k=None, sample=5000, run_id=None):
    if k is not None:
        raise ContractError("k is selected from evidence; fixed risk-group counts are unsupported")
    _, art = load_model("full", run_id)
    discovery = pd.read_parquet(art / "development.parquet")
    validation = pd.read_parquet(art / "policy_validation.parquet")
    pipe, selection = fit_segmenter(discovery, sample=sample or 5000)
    out = C.ARTIFACTS_DIR / "segmentation" / art.name
    rep = C.REPORTS_DIR / "segmentation" / art.name
    out.mkdir(parents=True, exist_ok=True); rep.mkdir(parents=True, exist_ok=True)
    predicted = pipe.predict(validation[SEG_FEATURES])
    summary = validation.assign(segment=[f"Segment {i + 1}" for i in predicted]).groupby("segment").agg(
        customers=(C.TARGET, "size"), observed_target_rate=(C.TARGET, "mean"))
    summary.to_csv(rep / "segment_summary.csv")
    pd.DataFrame(selection).to_csv(rep / "k_selection.csv", index=False)
    joblib.dump(pipe, out / "segmenter.joblib")
    write_json(out / "metadata.json", {"source_run": art.name, "feature_schema": "full-v1",
               "features": SEG_FEATURES, "discovery_partition": "development", "assessment_partition": "policy",
               "selection": selection, "labels": "descriptive; not approval/risk policy",
               "sha256": sha256(out / "segmenter.joblib")})
    return summary

