"""Validate the saved research benchmark without retraining any estimator."""
import json
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import xgboost_full_research as benchmark


@pytest.fixture(scope='module')
def saved():
    pointer = benchmark.OUTPUT / 'latest.json'
    if not pointer.exists():
        pytest.skip('Saved research benchmark not installed')
    run = benchmark.OUTPUT / json.loads(pointer.read_text())['run_id']
    return run, json.loads((run / 'metadata.json').read_text())


def test_saved_checksums_and_protected_artifacts(saved):
    run, meta = saved
    assert meta['mode'] == 'RESEARCH_ONLY' and meta['release_ready'] is False
    assert all(meta['validation'].values())
    for name, checksum in meta['artifact_checksums'].items():
        assert benchmark.sha256(run / name) == checksum, name
    assert benchmark.preserved_hashes() == json.loads((run / 'preserved_artifact_hashes.json').read_text())


def test_fold_partitions_have_no_overlap_and_model_reload_matches(saved):
    run, meta = saved
    baseline, features, parts, _ = benchmark.load_inputs()
    assert features == meta['feature_columns'] == baseline['feature_columns']
    assert len(features) == 22
    development = set(parts['development'].index)
    folds = json.loads((run / 'development_fold_lineage.json').read_text())
    assert len(folds) == 3
    assessments = []
    for fold in folds:
        groups = [set(fold[name]) for name in ('base', 'calibration', 'assessment')]
        assert set.union(*groups) == development
        assert sum(map(len, groups)) == len(development)
        assessments.extend(fold['assessment'])
    assert len(assessments) == len(set(assessments)) == len(development)
    model = joblib.load(run / 'xgboost_model.joblib')
    test = parts['test'].head(100)
    p = model['calibrator'].predict(model['pipeline'].predict_proba(test[features])[:, 1])
    paired = pd.read_parquet(run / 'paired_test_predictions.parquet').set_index('SK_ID_CURR')
    assert np.array_equal(p, paired.loc[test.index, 'xgboost_probability'].to_numpy())
    assert set(paired.index) == set(parts['test'].index)
    assert np.array_equal(paired.loc[parts['test'].index, 'TARGET'], parts['test']['TARGET'])
