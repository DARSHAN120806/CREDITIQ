"""Explain base-model output with explicit units; calibration is displayed separately."""
from __future__ import annotations
import logging
import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import shap
from sklearn.linear_model import LogisticRegression
from sklearn.tree import DecisionTreeClassifier
from sklearn.ensemble import RandomForestClassifier
from . import config as C
from .contracts import ContractError
from .provenance import load_model, write_json

log = logging.getLogger(__name__)


def _to_2d(sv, class_index=1):
    if isinstance(sv, list):
        return np.asarray(sv[class_index])
    values = np.asarray(sv)
    return values[:, :, class_index] if values.ndim == 3 else values


def _origin_map(model):
    prep = model.pipeline.named_steps["prep"]
    mapping = {}
    for name, transformer, columns in prep.transformers_:
        if name == "remainder":
            continue
        if name == "num":
            mapping.update(zip(transformer.get_feature_names_out(columns), columns))
        elif name == "cat":
            encoder = transformer.named_steps["ohe"]
            output = list(encoder.get_feature_names_out(columns))
            sources = [col for col, cats in zip(columns, encoder.categories_) for _ in cats]
            if len(output) != len(sources):
                raise ContractError("Encoder feature grouping mismatch")
            mapping.update(zip(output, sources))
    return mapping


class Explainer:
    def __init__(self, model, background_raw, n_background=200):
        self.model = model
        background = model.transform(background_raw.sample(min(n_background, len(background_raw)), random_state=C.SEED))
        self.cols = list(background.columns)
        self.origin = _origin_map(model)
        if set(self.cols) != set(self.origin):
            raise ContractError("Incomplete SHAP feature mapping")
        clf = model.classifier
        self.class_index = list(clf.classes_).index(1)
        if isinstance(clf, LogisticRegression):
            self.explainer = shap.LinearExplainer(clf, shap.maskers.Independent(background, max_samples=len(background)))
            self.explained_output = "raw_margin"
        else:
            # Native tree-path background: record this rather than claiming a supplied interventional reference.
            self.explainer = shap.TreeExplainer(clf, feature_perturbation="tree_path_dependent", model_output="raw")
            self.explained_output = "uncalibrated_probability" if isinstance(clf, (DecisionTreeClassifier, RandomForestClassifier)) else "raw_margin"
        ev = np.ravel(self.explainer.expected_value)
        self.base_value = float(ev[self.class_index] if len(ev) > 1 else ev[0])
        self.reference = "development_sample" if isinstance(clf, LogisticRegression) else "development_tree_path_distribution"

    def _output(self, Xt):
        clf = self.model.classifier
        if self.explained_output == "uncalibrated_probability":
            return clf.predict_proba(Xt)[:, self.class_index]
        if isinstance(clf, LogisticRegression):
            return clf.decision_function(Xt)
        if self.model.name == "xgboost":
            return clf.predict(Xt, output_margin=True)
        return clf.predict(Xt, raw_score=True)

    def shap_matrix(self, raw_df):
        Xt = self.model.transform(raw_df)
        values = _to_2d(self.explainer.shap_values(Xt), self.class_index)
        # Some native tree integrations set the learned base value on first evaluation.
        ev = np.ravel(self.explainer.expected_value)
        self.base_value = float(ev[self.class_index] if len(ev) > 1 else ev[0])
        expected = self._output(Xt)
        if values.shape != Xt.shape or not np.allclose(self.base_value + values.sum(axis=1), expected, rtol=1e-4, atol=1e-5):
            raise ContractError("SHAP output shape/additivity verification failed")
        return Xt, values

    def grouped(self, row):
        return pd.Series(row, index=self.cols).groupby(self.origin).sum()

    def explain(self, raw_row, top_k=5):
        if len(raw_row) != 1 or top_k < 1:
            raise ContractError("Explain exactly one applicant with positive top_k")
        Xt, values = self.shap_matrix(raw_row)
        grouped = self.grouped(values[0])
        total = float(grouped.abs().sum()) or 1.
        up = grouped[grouped > 0].nlargest(top_k)
        down = grouped[grouped < 0].nsmallest(top_k)
        def items(series):
            return [{"feature": name, "label": name.replace("_", " ").title(),
                     "contribution": float(v), "absolute_attribution_share_pct": 100 * abs(float(v)) / total}
                    for name, v in series.items()]
        remainder = float(grouped.sum() - up.sum() - down.sum())
        return {"target_class": 1, "model_version": self.model.meta.get("run_id"),
                "feature_schema_version": self.model.schema_version, "explainer_version": shap.__version__,
                "explained_output": self.explained_output, "reference": self.reference,
                "base_value": self.base_value, "explained_value": float(self._output(Xt)[0]),
                "calibrated_pd": float(self.model.predict_proba(raw_row)[0]),
                "calibration_explained": False, "increases_risk": items(up), "reduces_risk": items(down),
                "remainder_contribution": remainder,
                "additivity_error": float(self.base_value + grouped.sum() - self._output(Xt)[0])}


def run_explain(feature_set="lite", n_samples=1500, run_id=None):
    model, art = load_model(feature_set, run_id)
    rep = C.REPORTS_DIR / "explain" / feature_set / art.name
    rep.mkdir(parents=True, exist_ok=True)
    background = pd.read_parquet(art / "explanation_background.parquet")
    sample = pd.read_parquet(art / "explanation_sample.parquet").head(n_samples)
    ex = Explainer(model, background)
    Xt, values = ex.shap_matrix(sample)
    grouped = pd.DataFrame(values, columns=ex.cols).T.groupby(ex.origin).sum().T
    importance = grouped.abs().mean().sort_values(ascending=False)
    importance.to_csv(rep / "global_importance.csv", header=["mean_abs_shap"])
    top = importance.head(20).iloc[::-1]
    plt.figure(figsize=(8, 7)); plt.barh(top.index, top.values); plt.tight_layout()
    plt.savefig(rep / "shap_importance.png"); plt.close()
    shap.summary_plot(values, Xt, max_display=20, show=False)
    plt.tight_layout(); plt.savefig(rep / "shap_beeswarm.png", bbox_inches="tight"); plt.close()
    write_json(rep / "example_explanation.json", ex.explain(sample.iloc[[0]]))
    return importance

