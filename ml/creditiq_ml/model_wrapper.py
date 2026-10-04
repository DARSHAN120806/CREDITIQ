"""Stable artifact import path; strict features plus calibration, separate policy."""
from __future__ import annotations
import numpy as np
import pandas as pd
from .contracts import ContractError, CATEGORICAL, feature_names, validate_features, request_features
from .risk import DecisionPolicy, probability, risk_score, risk_band, credit_health_score


class CreditRiskModel:
    def __init__(self, name, pipeline, calibrator, feature_columns, categorical_columns,
                 reject_at=None, approve_below=None, meta=None):
        if reject_at is not None or approve_below is not None:
            raise ContractError("Thresholds belong to DecisionPolicy; retrain legacy models")
        self.name = name
        self.pipeline = pipeline
        self.calibrator = calibrator
        self.feature_columns = list(feature_columns)
        self.categorical_columns = list(categorical_columns)
        self.meta = meta or {}
        self.variant = self.meta.get("feature_set", "lite")
        if self.feature_columns != feature_names(self.variant):
            raise ContractError("Model feature contract differs from design")
        self.schema_version = f"{self.variant}-v1"
        self.reference_probabilities = np.array([], dtype=float)

    def _prepare(self, X):
        if getattr(self, "schema_version", None) != f"{getattr(self, 'variant', '')}-v1":
            raise ContractError("Legacy artifact: retraining required")
        return validate_features(X, self.variant)

    @property
    def classifier(self):
        return self.pipeline[-1]

    def transform(self, X):
        return self.pipeline[:-1].transform(self._prepare(X))

    def raw_proba(self, X):
        classes = list(self.classifier.classes_)
        if classes != [0, 1]:
            raise ContractError("Expected binary target classes [0,1]")
        return self.pipeline.predict_proba(self._prepare(X))[:, classes.index(1)]

    def predict_proba(self, X):
        """One-dimensional calibrated positive-class PD (intentional legacy interface)."""
        p = np.asarray(self.calibrator.predict(self.raw_proba(X)))
        if not np.isfinite(p).all() or ((p < 0) | (p > 1)).any():
            raise ContractError("Invalid calibrated output")
        return p

    def support_flags(self, X):
        x = self._prepare(X)
        observed = self.meta.get("observed_categories", {})
        flags = []
        for _, row in x.iterrows():
            row_flags = []
            for c in CATEGORICAL:
                if row[c] == "OTHER" or row[c] not in observed.get(c, []):
                    row_flags.append(f"unsupported_category:{c}")
            for c, bounds in self.meta.get("numeric_support", {}).items():
                if pd.notna(row[c]) and (row[c] < bounds[0] or row[c] > bounds[1]):
                    row_flags.append(f"outside_development_range:{c}")
            if pd.isna(row.years_employed) and not self.meta.get("tenure_missing_observed", False):
                row_flags.append("unseen_missing_tenure")
            flags.append(row_flags)
        return flags

    def score_request(self, payload, *, quote, policy=None, history=None, schedule=None, source_context=None, **decision_context):
        x = request_features(payload, currency=self.meta.get("currency"), quote=quote)
        if self.variant == "full":
            from .contracts import HISTORY_FEATURES
            from .features import history_features
            if history is None or source_context is None or schedule is None:
                raise ContractError("Full scoring requires trusted history and source evidence")
            if source_context.get("as_of") != payload["as_of"] or "customer_id" not in source_context:
                raise ContractError("Full history cutoff/completeness mismatch")
            aggregate = history_features([source_context["customer_id"]], history, schedule, source_context).iloc[0]
            for col in HISTORY_FEATURES:
                x[col] = [aggregate[col]]
        p = float(self.predict_proba(x)[0])
        flags = self.support_flags(x)[0]
        policy = policy or DecisionPolicy()
        decision_context.pop("supported", None)
        decision_context.pop("release_ready", None)
        decision = policy.evaluate(p, variant=self.variant, model_version=self.meta.get("run_id"),
                                   release_ready=self.meta.get("release_ready", False),
                                   supported=not flags, **decision_context)
        reference = np.sort(self.reference_probabilities)
        percentile = float(100 * np.searchsorted(reference, p, side="right") / len(reference)) if len(reference) else None
        return {"model_variant": self.variant.upper(), "model_version": self.meta.get("run_id"),
                "feature_schema_version": self.schema_version, "calibration_version": self.meta.get("calibration_method"),
                "target_definition_version": self.meta.get("target_definition_version"),
                "application_version": payload["application_version"], "scored_at": payload["as_of"],
                "calibrated_pd": p, "risk_score": risk_score(p), "risk_band": risk_band(p),
                "credit_health_index": credit_health_score(p), "reference_percentile": percentile,
                "data_quality_flags": flags, "explanation_status": "PENDING", **decision}

    def decide(self, p, policy=None, **context):
        if not hasattr(self, "schema_version"):
            raise ContractError("Legacy artifact: retraining required")
        return (policy or DecisionPolicy()).evaluate(probability(p), variant=self.variant,
                model_version=self.meta.get("run_id"), release_ready=self.meta.get("release_ready", False),
                **context)["decision_status"]

