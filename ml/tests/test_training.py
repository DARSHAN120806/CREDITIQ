import json
import joblib
import numpy as np
import pandas as pd
import pytest
from creditiq_ml import config as C
from creditiq_ml.contracts import ContractError, LITE_FEATURES, FULL_FEATURES
from creditiq_ml.features import build_feature_table
from creditiq_ml.train import (split_cohorts, train_all, make_pipeline, ProbabilityCalibrator,
                               FoldBalancedXGBClassifier, GRIDS)
from creditiq_ml.preprocessing import split_columns
from creditiq_ml.model_wrapper import CreditRiskModel
from creditiq_ml.provenance import load_model, release_dir


def test_partition_identities_disjoint_and_stable(data_root):
    lite = build_feature_table(feature_set="lite")
    full = build_feature_table(feature_set="full")
    a = split_cohorts(lite[lite.IS_TRAIN.eq(1)])
    b = split_cohorts(full[full.IS_TRAIN.eq(1)])
    assert a == b
    groups = list(a.values())
    assert sum(map(len, groups)) == len(set(sum(groups, []))) == 600
    assert [len(a[k]) for k in ("development", "calibration", "policy", "test")] == [360, 90, 60, 90]


def test_complete_training_metadata_reload_and_separation(data_root, monkeypatch):
    monkeypatch.setitem(GRIDS, "logistic_regression", {"clf__C": [.2]})
    comparison = train_all("lite", n_trials=1, models=["logistic_regression"], tune_rows=500)
    model, path = load_model("lite")
    metadata = json.loads((path / "metadata.json").read_text())
    assert metadata["n_features_in"] == 17
    assert metadata["release_ready"] is False
    assert metadata["synthetic"] is True
    assert "AveragePrecision" in metadata["test_metrics"]["metrics"]
    assert set(comparison.Calibration) == {"sigmoid", "isotonic"}
    ids = json.loads((path / "splits.json").read_text())
    folds = json.loads((path / "development_folds.json").read_text())
    for fold in folds:
        a, b, c = map(set, (fold["base"], fold["calibration"], fold["assessment"]))
        assert not a & b and not a & c and not b & c
        assert a | b | c == set(ids["development"])
    sample = pd.read_parquet(path / "explanation_background.parquet")
    predictions = model.predict_proba(sample)
    assert np.isfinite(predictions).all() and ((0 <= predictions) & (predictions <= 1)).all()
    assert np.array_equal(predictions, joblib.load(path / "best_model.joblib").predict_proba(sample))
    assert model.decide(.001) == model.decide(.99) == "MANUAL_REVIEW"
    with pytest.raises(ContractError):
        model.predict_proba(sample.drop(columns="annual_income"))
    # Explanation background is development data, not the saved test predictions.
    assert not set(ids["development"]) & set(ids["test"])
    from creditiq_ml.explain import Explainer
    explanation = Explainer(model, sample).explain(sample.iloc[[0]])
    assert explanation["explained_output"] == "raw_margin"
    assert explanation["calibration_explained"] is False
    assert abs(explanation["additivity_error"]) < 1e-5


@pytest.mark.parametrize("name", ["decision_tree", "random_forest", "xgboost", "lightgbm"])
def test_classifier_calibration_and_shap_units(data_root, name):
    from creditiq_ml.explain import Explainer
    df = build_feature_table(feature_set="lite").query("IS_TRAIN == 1")
    X, y = df[LITE_FEATURES], df.TARGET.astype(int)
    num, cat = split_columns(X)
    params = {"n_estimators": 5} if name in ("xgboost", "lightgbm") else {"max_depth": 3}
    pipe = make_pipeline(name, params, num, cat, 1).fit(X.iloc[:300], y.iloc[:300])
    cal = ProbabilityCalibrator("sigmoid").fit(pipe.predict_proba(X.iloc[300:450])[:, 1], y.iloc[300:450])
    model = CreditRiskModel(name, pipe, cal, LITE_FEATURES, cat, meta={"feature_set": "lite"})
    ex = Explainer(model, X.iloc[:100])
    output = ex.explain(X.iloc[[500]])
    assert output["explained_output"] == ("uncalibrated_probability" if name in ("decision_tree", "random_forest") else "raw_margin")
    assert abs(output["additivity_error"]) < 1e-4


def test_segmentation_roundtrip(data_root, tmp_path):
    from creditiq_ml.segmentation import fit_segmenter, SEG_FEATURES
    df = build_feature_table(feature_set="full")
    pipeline, evidence = fit_segmenter(df.iloc[:400], sample=300)
    before = pipeline.predict(df.iloc[400:][SEG_FEATURES])
    path = tmp_path / "seg.joblib"
    joblib.dump(pipeline, path)
    after = joblib.load(path).predict(df.iloc[400:][SEG_FEATURES])
    assert np.array_equal(before, after)
    assert len(evidence) > 1
    assert hasattr(pipeline.named_steps["prep"].named_steps["clip"], "lo_")


@pytest.mark.parametrize("name", ["xgboost", "lightgbm"])
def test_optuna_path_and_fold_weights(data_root, monkeypatch, name):
    import creditiq_ml.train as training
    df = build_feature_table(feature_set="lite").query("IS_TRAIN == 1")
    X, y = df[LITE_FEATURES].iloc[:300], df.TARGET.iloc[:300].astype(int)
    num, cat = split_columns(X)
    def tiny_space(model_name, trial):
        return {"n_estimators": trial.suggest_int("n_estimators", 3, 3), "max_depth": 2}
    monkeypatch.setattr(training, "optuna_space", tiny_space)
    params, auc = training.tune(name, X, y, num, cat, 999, 1)
    assert params["n_estimators"] == 3 and 0 <= auc <= 1
    if name == "xgboost":
        model = training.make_estimator(name, {"n_estimators": 3}, 999)
        model.fit(np.arange(len(y)).reshape(-1, 1), y)
        assert model.get_params()["scale_pos_weight"] == pytest.approx((y == 0).sum() / (y == 1).sum())
