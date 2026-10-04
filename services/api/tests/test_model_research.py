"""Saved XGBoost benchmark presentation and provenance validation; no training."""
import json

import pytest
from fastapi import HTTPException
from app.services import model_research as research


def test_xgboost_saved_comparison_and_ranking():
    payload = research.load_dashboard()
    benchmark = payload['xgboost_benchmark']
    assert payload['mode'] == 'RESEARCH_ONLY' and payload['release_ready'] is False
    assert benchmark['feature_count'] == 22 and benchmark['test_rows'] == 41733
    assert [row['model'] for row in benchmark['metrics']] == ['LightGBM', 'XGBoost']
    first, second = benchmark['metrics']
    for key in ('roc_auc', 'average_precision', 'brier_score', 'log_loss'):
        assert benchmark['metric_deltas'][key] == pytest.approx(second[key] - first[key])
    assert [row['model'] for row in benchmark['ranking']] == [row['model'] for row in sorted(
        benchmark['metrics'], key=lambda row: (row['brier_score'], -row['roc_auc'], row['model']))]
    assert len(benchmark['calibration']['bins']) == 20
    assert {row['Calibration'] for row in benchmark['calibration']['development_selection']} == {'sigmoid', 'isotonic'}
    assert len(benchmark['shap']['top_features']) == 20
    assert 'previously inspected' in benchmark['evaluation_note']
    assert 'no promotion' in benchmark['ranking_basis']


def test_missing_optional_benchmark_preserves_original_dashboard(monkeypatch, tmp_path):
    monkeypatch.setattr(research, 'XGBOOST_ROOT', tmp_path)
    payload = research.load_dashboard()
    assert payload['xgboost_benchmark'] is None
    assert [row['name'] for row in payload['metrics']] == ['Lite', 'FULL_RESEARCH_V1_NO_EXT']


@pytest.mark.parametrize('field,value', [
    ('baseline_run_id', 'different'), ('feature_columns', ['wrong']), ('release_ready', True),
    ('mode', 'PRODUCTION'), ('split_sizes', {'test': 1}), ('best_model', 'lightgbm'),
])
def test_mismatched_benchmark_provenance_fails_closed(monkeypatch, tmp_path, field, value):
    pointer = json.loads((research.XGBOOST_ROOT / 'latest.json').read_text())
    meta = json.loads((research.XGBOOST_ROOT / pointer['run_id'] / 'metadata.json').read_text())
    meta[field] = value
    (tmp_path / 'latest.json').write_text(json.dumps(pointer))
    folder = tmp_path / pointer['run_id']
    folder.mkdir()
    (folder / 'metadata.json').write_text(json.dumps(meta))
    monkeypatch.setattr(research, 'XGBOOST_ROOT', tmp_path)
    with pytest.raises(HTTPException) as exc:
        research.load_dashboard()
    assert exc.value.status_code == 503


def test_benchmark_pointer_cannot_escape_root(monkeypatch, tmp_path):
    (tmp_path / 'latest.json').write_text(json.dumps({'run_id': '../../elsewhere'}))
    monkeypatch.setattr(research, 'XGBOOST_ROOT', tmp_path)
    with pytest.raises(HTTPException) as exc:
        research.load_dashboard()
    assert exc.value.status_code == 503
