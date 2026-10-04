"""Isolated XGBoost benchmark; reads the pinned NO_EXT data and LightGBM results.

Run from ml/: .venv/Scripts/python.exe -u tools/xgboost_full_research.py
Existing contracts, artifacts, and prediction paths are never written.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import logging
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import joblib
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import xgboost as xgb

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from creditiq_ml import config as C
from creditiq_ml.preprocessing import split_columns
from creditiq_ml.train import ProbabilityCalibrator, make_pipeline, select_on_development, tune
from full_research_v1_no_ext import calibration_metrics

BASELINE_ID = '20261004T075100Z'
BASELINE = ROOT / 'research_output/full_research_v1_no_ext' / BASELINE_ID
LITE = ROOT / 'real_data_output/artifacts/lite/runs/20261002T140817Z-045430a7'
OUTPUT = ROOT / 'research_output/xgboost_full_research_v1_no_ext'
METRICS = ('roc_auc', 'average_precision', 'brier_score', 'log_loss')
TEST_NOTE = ('Same pinned final-test applicants as the existing LightGBM experiment. '
             'This cohort was previously inspected; results are a reused-holdout research benchmark, '
             'not new independent confirmation. No selection uses these test results.')


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def sha256(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def preserved_hashes():
    roots = [ROOT / 'real_data_output/artifacts', ROOT / 'research_output/full_research_v1_no_ext',
             ROOT / 'research_output/customer_segmentation', ROOT / 'research_contracts']
    return {str(path.relative_to(ROOT)): sha256(path)
            for folder in roots for path in sorted(folder.rglob('*')) if path.is_file()}


def load_inputs():
    meta = json.loads((BASELINE / 'metadata.json').read_text())
    contract = json.loads((BASELINE / 'FULL_RESEARCH_V1_NO_EXT.json').read_text())
    features = meta['feature_columns']
    # The legacy contract's top-level features array is stale; use the exact fitted
    # column list, cross-checked against its 22 authoritative feature definitions.
    if (meta['run_id'] != BASELINE_ID or meta['contract'] != 'FULL_RESEARCH_V1_NO_EXT'
            or features != [row['name'] for row in contract['feature_definitions']]
            or len(features) != 22 or any('ext_source' in name.lower() for name in features)):
        raise ValueError('Pinned 22-feature contract mismatch')
    data = pd.read_parquet(BASELINE / 'full_research_v1_no_ext_train.parquet')
    if list(data.columns) != [C.ID_COL, *features, C.TARGET]:
        raise ValueError('Source parquet columns/order do not match the fitted contract')
    if data[C.ID_COL].isna().any() or data[C.ID_COL].duplicated().any() or not data[C.TARGET].isin([0, 1]).all():
        raise ValueError('Invalid source identities or target labels')
    data = data.set_index(C.ID_COL)
    splits = json.loads((LITE / 'splits.json').read_text())
    if set(splits) != {'development', 'calibration', 'policy', 'test'}:
        raise ValueError('Unexpected partitions')
    all_ids = [value for values in splits.values() for value in values]
    if len(all_ids) != len(set(all_ids)) or set(all_ids) != set(data.index):
        raise ValueError('Partitions must be disjoint and exhaust the same source applicants')
    parts = {name: data.loc[ids] for name, ids in splits.items()}
    if {name: len(part) for name, part in parts.items()} != meta['split_sizes']:
        raise ValueError('Partition sizes differ from the LightGBM baseline')
    if any(part[C.TARGET].nunique() != 2 for part in parts.values()):
        raise ValueError('Every partition requires both target classes')
    paired = pd.read_parquet(BASELINE / 'paired_test_predictions.parquet').set_index(C.ID_COL)
    if paired.index.duplicated().any() or set(paired.index) != set(splits['test']):
        raise ValueError('LightGBM prediction identities differ from the pinned test set')
    paired = paired.loc[parts['test'].index]
    if not np.array_equal(paired[C.TARGET], parts['test'][C.TARGET]):
        raise ValueError('Paired test labels differ')
    observed = calibration_metrics(paired[C.TARGET], paired.no_ext_probability)
    for metric in METRICS:
        if not np.isclose(observed[metric], meta['test_metrics']['FULL_RESEARCH_V1_NO_EXT'][metric], atol=1e-12, rtol=0):
            raise ValueError('Saved LightGBM probabilities and metrics disagree')
    return meta, features, parts, paired


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--resume-run', help='Finish reporting an already saved XGBoost model without retraining')
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')
    before = preserved_hashes()
    meta, features, parts, baseline_predictions = load_inputs()
    run_id = args.resume_run or datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    if not re.fullmatch(r'\d{8}T\d{6}Z', run_id):
        raise ValueError('Invalid run ID')
    output = OUTPUT / run_id
    dev, cal, test = (parts[key] for key in ('development', 'calibration', 'test'))
    X, y = dev[features], dev[C.TARGET].astype(int)
    budget = json.loads((LITE / 'metadata.json').read_text())['search_budget']
    trials, tune_rows = int(budget['optuna_trials']), int(budget['tune_rows'])
    if args.resume_run:
        saved = json.loads((output / 'training_metadata.json').read_text())
        if saved['protected_inputs_sha256'] != before:
            raise ValueError('Protected inputs changed since this training run')
        artifact = joblib.load(output / 'xgboost_model.joblib')
        model, calibrator, method = artifact['pipeline'], artifact['calibrator'], artifact['calibration_method']
        if artifact['feature_columns'] != features:
            raise ValueError('Saved estimator features differ from baseline')
        params, cv_auc = saved['params'], saved['development_cv_auc']
    else:
        output.mkdir(parents=True, exist_ok=False)
        write_json(output / 'preserved_artifact_hashes.json', before)
        logging.info('Run %s: nested development selection, XGBoost only', run_id)
        selection, folds, lineage = select_on_development(X, y, ['xgboost'], trials, tune_rows)
        selection.to_csv(output / 'development_model_selection.csv', index=False)
        folds.to_csv(output / 'development_selection_folds.csv', index=False)
        write_json(output / 'development_fold_lineage.json', lineage)
        method = str(selection.iloc[0].Calibration)
        num, cat = split_columns(X)
        logging.info('Final tuning on all %d development rows, matching LightGBM script', len(X))
        params, cv_auc = tune('xgboost', X, y, num, cat, 1.0, trials)
        logging.info('Final XGBoost fitting, followed by disjoint %s calibration', method)
        model = make_pipeline('xgboost', params, num, cat, 1.0).fit(X, y)
        calibrator = ProbabilityCalibrator(method).fit(model.predict_proba(cal[features])[:, 1], cal[C.TARGET])
        joblib.dump({'pipeline': model, 'calibrator': calibrator, 'feature_columns': features,
                     'calibration_method': method}, output / 'xgboost_model.joblib')
        write_json(output / 'training_metadata.json', {
            'params': params, 'development_cv_auc': cv_auc, 'protected_inputs_sha256': before})

    logging.info('Evaluating fixed calibrated model on the pinned test partition')
    probability = calibrator.predict(model.predict_proba(test[features])[:, 1])
    if not np.isfinite(probability).all() or not ((probability >= 0) & (probability <= 1)).all():
        raise ValueError('Invalid calibrated probabilities')
    baseline_probability = baseline_predictions.no_ext_probability.to_numpy()
    results = {'LightGBM': calibration_metrics(test[C.TARGET], baseline_probability),
               'XGBoost': calibration_metrics(test[C.TARGET], probability)}
    comparison = pd.DataFrame([{'model': name, **{key: values[key] for key in METRICS}}
                               for name, values in results.items()])
    comparison.to_csv(output / 'model_comparison.csv', index=False)
    deltas = {key: results['XGBoost'][key] - results['LightGBM'][key] for key in METRICS}
    write_json(output / 'model_comparison.json', {'test_rows': len(test), 'evaluation': TEST_NOTE,
               'models': results, 'xgboost_minus_lightgbm': deltas})
    pair = pd.DataFrame({C.ID_COL: test.index, C.TARGET: test[C.TARGET].to_numpy(),
                         'lightgbm_probability': baseline_probability, 'xgboost_probability': probability,
                         'probability_difference': probability - baseline_probability})
    pair.to_parquet(output / 'paired_test_predictions.parquet', index=False)
    pair.to_csv(output / 'paired_test_predictions.csv', index=False)
    selection = pd.read_csv(output / 'development_model_selection.csv')
    write_json(output / 'calibration_results.json', {
        'cohort': TEST_NOTE, 'selection_basis': 'Development nested CV: lowest mean Brier, then highest ROC-AUC',
        'development_selection': selection.to_dict('records'), 'selected_method': method,
        'baseline_method': meta['calibration_method'],
        'LightGBM': results['LightGBM']['calibration_bins'], 'XGBoost': results['XGBoost']['calibration_bins']})
    plt.figure(figsize=(7, 6))
    for name, values in results.items():
        bins = values['calibration_bins']
        plt.plot([row['mean_predicted_probability'] for row in bins],
                 [row['observed_default_rate'] for row in bins], marker='o', label=name)
    plt.plot([0, .3], [0, .3], '--', color='gray', label='Ideal')
    plt.xlabel('Mean predicted probability'); plt.ylabel('Observed outcome rate'); plt.legend()
    plt.title('Shared research test cohort (previously inspected)'); plt.tight_layout()
    plt.savefig(output / 'calibration_comparison.png', dpi=150); plt.close()

    logging.info('Computing native exact Tree SHAP on the same deterministic 1,000-row sample')
    sample = test[features].sample(min(1000, len(test)), random_state=C.SEED)
    transformed = model.named_steps['prep'].transform(sample)
    booster = model.named_steps['clf'].get_booster()
    matrix = xgb.DMatrix(transformed)
    contributions = booster.predict(matrix, pred_contribs=True, approx_contribs=False)
    margins = booster.predict(matrix, output_margin=True)
    names = list(model.named_steps['prep'].get_feature_names_out())
    if contributions.shape != (len(sample), len(names) + 1) or not np.allclose(
            contributions.sum(axis=1), margins, rtol=1e-4, atol=1e-5):
        raise ValueError('Native Tree SHAP dimensions or additivity failed')
    importance = pd.DataFrame({'feature': names, 'mean_abs_shap_raw_margin':
                               np.abs(contributions[:, :-1]).mean(axis=0)}).sort_values(
                                   'mean_abs_shap_raw_margin', ascending=False)
    importance.to_csv(output / 'shap_feature_importance.csv', index=False)
    importance.head(20).to_csv(output / 'top_20_features.csv', index=False)
    plt.figure(figsize=(9, 8)); shown = importance.head(20).iloc[::-1]
    plt.barh(shown.feature, shown.mean_abs_shap_raw_margin, color='#6366f1')
    plt.xlabel('Mean absolute Tree SHAP (uncalibrated raw margin)'); plt.tight_layout()
    plt.savefig(output / 'shap_top_20.png', dpi=150); plt.close()

    restored = joblib.load(output / 'xgboost_model.joblib')
    reloaded_p = restored['calibrator'].predict(restored['pipeline'].predict_proba(test[features].head(100))[:, 1])
    if not np.array_equal(reloaded_p, probability[:100]):
        raise ValueError('Reloaded artifact prediction parity failed')
    after = preserved_hashes()
    if before != after:
        raise ValueError('A protected artifact changed during the benchmark')
    ranking = comparison.sort_values(['brier_score', 'roc_auc', 'model'], ascending=[True, False, True]).model.tolist()
    ranking_basis = 'Descriptive test Brier ascending, ROC-AUC descending tie-break; no promotion or model selection.'
    metadata = {
        'run_id': run_id, 'contract': 'FULL_RESEARCH_V1_NO_EXT', 'feature_count': 22,
        'feature_columns': features, 'baseline_run_id': BASELINE_ID, 'best_model': 'xgboost',
        'trained_at': datetime.now(timezone.utc).isoformat(), 'params': params,
        'calibration_method': method, 'development_cv_auc': cv_auc,
        'split_sizes': {key: len(value) for key, value in parts.items()},
        'split_source': str((LITE / 'splits.json').relative_to(ROOT)),
        'dataset_sha256': sha256(BASELINE / 'full_research_v1_no_ext_train.parquet'),
        'splits_sha256': sha256(LITE / 'splits.json'),
        'search_budget': {'optuna_trials': trials, 'outer_tune_rows': tune_rows,
                          'final_tune_rows': len(dev), 'seed': C.SEED},
        'test_metrics': results, 'test_evaluation_note': TEST_NOTE, 'metric_deltas': deltas,
        'research_ranking': ranking, 'ranking_basis': ranking_basis,
        'shap_interpretation': 'Native exact Tree SHAP explains uncalibrated XGBoost raw margins, not calibrated probabilities or causal effects.',
        'validation': {'protected_artifacts_unchanged': True, 'protected_file_count': len(before),
                       'model_reload_parity': True, 'shap_additivity': True,
                       'same_contract_partitions_labels': True},
        'versions': {package: importlib.metadata.version(package) for package in
                     ('xgboost', 'scikit-learn', 'numpy', 'pandas', 'optuna', 'joblib')},
        'mode': 'RESEARCH_ONLY', 'release_ready': False,
    }
    metadata['artifact_checksums'] = {path.name: sha256(path) for path in output.iterdir()
                                    if path.is_file() and path.name not in ('metadata.json', 'XGBOOST_FULL_RESEARCH_REPORT.md')}
    write_json(output / 'metadata.json', metadata)
    lines = ['# XGBoost FULL_RESEARCH_V1_NO_EXT benchmark', '',
             f'Run: `{run_id}`. Baseline: `{BASELINE_ID}`. `mode=RESEARCH_ONLY`; `release_ready=false`.', '',
             '## Methodology', '',
             'Exactly 22 fitted LightGBM contract features and the same 278,220 eligible labeled applicants. '
             'Pinned disjoint development/calibration/policy/test sizes: 166,932 / 41,733 / 27,822 / 41,733. '
             'Policy is preserved and unused in selection. Dataset and partition hashes are in metadata.', '',
             f'Three outer development folds; five Optuna trials per inner three-fold search. '
             f'Outer tuning subsamples: {tune_rows:,} rows. Final tuning uses all {len(dev):,} development rows, '
             'matching the existing LightGBM runner. Preprocessing is refitted within each fold; class imbalance '
             'weights use only fitting labels. Sigmoid/isotonic selection minimizes development Brier, then maximizes ROC-AUC. '
             f'Selected calibration: **{method}**, fitted only on the separate calibration partition.', '',
             TEST_NOTE, '', 'Only XGBoost estimators were trained. Sigmoid calibration uses the existing logistic '
             'calibration component; no standalone Logistic Regression benchmark was trained.', '',
             '## Paired final-test metrics', '',
             '| Model | ROC-AUC | Average Precision | Brier | Log loss |', '|---|---:|---:|---:|---:|']
    for name, values in results.items():
        lines.append('| ' + name + ' | ' + ' | '.join(f'{values[key]:.6f}' for key in METRICS) + ' |')
    lines += ['', 'XGBoost minus LightGBM: ' + ', '.join(f'{key} {value:+.6f}' for key, value in deltas.items()),
              '', '## Descriptive ranking', '', f"{' > '.join(ranking)}. {ranking_basis}", '',
              'Point estimates alone do not establish a meaningful improvement. This reused test set does not '
              'provide external or prospective validation.', '', '## Calibration and explanations', '',
              'Saved development selection/fold results document both calibration candidates. Calibration JSON and PNG '
              'show ten quantile reliability bins for each final probability model. Native XGBoost exact Tree SHAP '
              'uses the same deterministic 1,000-row test sample as LightGBM; dimensions and raw-margin additivity '
              'are verified. Absolute attributions describe magnitude, not direction or causality.', '',
              '## Validation and preservation', '',
              f'Model reload and fixed-sample probability parity passed. {len(before)} protected files have identical '
              'before/after SHA-256 hashes. Existing Lite, LightGBM, segmentation, and contracts were not modified.', '',
              '## Limitations', '',
              'The baseline contract contains a stale top-level features array. This run uses its 22 feature_definitions '
              'cross-checked against the fitted model metadata and source parquet, without modifying the existing contract. '
              'Source units/time periods, target horizon, bureau-inquiry availability, fairness, temporal stability, and '
              'external validation remain unresolved. No applicant scoring or lending decisions are authorized.', '',
              '## Artifacts', '',
              'xgboost_model.joblib, metadata.json, model_comparison.csv/json, calibration_results.json, '
              'calibration_comparison.png, shap_feature_importance.csv, top_20_features.csv, shap_top_20.png, '
              'paired_test_predictions.parquet/csv, development_model_selection.csv, development_selection_folds.csv, '
              'development_fold_lineage.json, and preserved_artifact_hashes.json.', '']
    (output / 'XGBOOST_FULL_RESEARCH_REPORT.md').write_text('\n'.join(lines), encoding='utf-8')
    write_json(OUTPUT / 'latest.json', {'run_id': run_id})
    print(json.dumps({'run_id': run_id, 'metrics': comparison.to_dict('records'), 'calibration': method,
                      'ranking': ranking, 'validation': metadata['validation']}, indent=2))


if __name__ == '__main__':
    main()
