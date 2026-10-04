"""Read-only view of pinned model research reports; never loads or runs estimators."""
import csv
import json
import math
import re
from pathlib import Path

from fastapi import HTTPException

ROOT = Path(__file__).resolve().parents[4]
LITE_ROOT = ROOT / 'ml/real_data_output'
RESEARCH_ROOT = ROOT / 'ml/research_output/full_research_v1_no_ext'
XGBOOST_ROOT = ROOT / 'ml/research_output/xgboost_full_research_v1_no_ext'
GROUPS = {
    'Application': {'age_years', 'household_size', 'dependent_children', 'education_level', 'housing_status'},
    'Employment': {'years_employed', 'employment_type', 'occupation', 'employment_tenure_missing', 'employed_age_ratio'},
    'Affordability': {'annual_income', 'requested_amount', 'quoted_monthly_payment', 'proposed_payment_income_ratio',
                      'principal_income_ratio', 'income_per_household_member', 'payment_principal_ratio'},
    'Borrowing History': {'credit_bureau_inquiries_1m', 'credit_bureau_inquiries_3m',
                          'credit_bureau_inquiries_12m', 'credit_bureau_inquiry_history_missing'},
    'Debt Exposure': {'loan_to_goods_price_ratio'},
}
LIMITATIONS = [
    'RESEARCH_ONLY; not production approved and not for lending decisions.',
    'External validation has not been completed; evaluation uses one shared held-out Home Credit cohort.',
    'Bureau inquiry availability for real applicants remains unresolved.',
    'Target population and outcome horizon are not independently established.',
    'SHAP values describe model associations on the raw margin; they are not causal explanations.',
]


def _json(path: Path) -> dict:
    with path.open(encoding='utf-8') as file:
        return json.load(file)


def _csv(path: Path) -> list[dict]:
    with path.open(encoding='utf-8-sig', newline='') as file:
        return list(csv.DictReader(file))


def _run_id(path: Path, pattern: str) -> str:
    run_id = _json(path).get('run_id', '')
    if not re.fullmatch(pattern, run_id):
        raise ValueError(f'Invalid artifact run pointer: {path.name}')
    return run_id


def _group_features(features: list[str]) -> list[dict]:
    remaining = set(features)
    grouped = []
    for name, members in GROUPS.items():
        selected = [feature for feature in features if feature in members]
        remaining.difference_update(selected)
        if selected:
            grouped.append({'name': name, 'features': selected})
    if remaining:
        raise ValueError(f'Feature contract contains unmapped features: {sorted(remaining)}')
    return grouped


def _xgboost_benchmark(baseline: dict) -> dict | None:
    """Optional saved benchmark; no estimator loading or inference."""
    if not (XGBOOST_ROOT / 'latest.json').exists():
        return None
    run_id = _run_id(XGBOOST_ROOT / 'latest.json', r'\d{8}T\d{6}Z')
    folder = XGBOOST_ROOT / run_id
    meta = _json(folder / 'metadata.json')
    if (meta.get('run_id') != run_id or meta.get('baseline_run_id') != baseline['run_id']
            or meta.get('contract') != baseline['contract'] or meta.get('best_model') != 'xgboost'
            or meta.get('feature_columns') != baseline['feature_columns']
            or meta.get('feature_count') != 22 or meta.get('split_sizes') != baseline['split_sizes']
            or meta.get('mode') != 'RESEARCH_ONLY' or meta.get('release_ready') is not False):
        raise ValueError('XGBoost benchmark provenance differs from the pinned baseline')
    rows = _csv(folder / 'model_comparison.csv')
    if [row['model'] for row in rows] != ['LightGBM', 'XGBoost']:
        raise ValueError('Unexpected benchmark model comparison')
    keys = ('roc_auc', 'average_precision', 'brier_score', 'log_loss')
    comparison = [{'model': row['model'], **{key: float(row[key]) for key in keys}} for row in rows]
    for row in comparison:
        for key in keys:
            if not math.isfinite(row[key]) or not math.isclose(
                    row[key], meta['test_metrics'][row['model']][key], abs_tol=1e-12, rel_tol=0):
                raise ValueError('Benchmark CSV disagrees with saved metadata')
    baseline_metrics = baseline['test_metrics']['FULL_RESEARCH_V1_NO_EXT']
    if any(not math.isclose(comparison[0][key], baseline_metrics[key], abs_tol=1e-12, rel_tol=0) for key in keys):
        raise ValueError('Benchmark LightGBM metrics differ from the existing run')
    calibration = _json(folder / 'calibration_results.json')
    bins = [{'model': name, 'bin': index, **row} for name in ('LightGBM', 'XGBoost')
            for index, row in enumerate(calibration[name], 1)]
    shap = [{'feature': row['feature'], 'mean_abs_shap_raw_margin': float(row['mean_abs_shap_raw_margin'])}
            for row in _csv(folder / 'shap_feature_importance.csv')]
    ranking = sorted(comparison, key=lambda row: (row['brier_score'], -row['roc_auc'], row['model']))
    return {
        'run_id': run_id, 'feature_count': 22, 'baseline_run_id': baseline['run_id'],
        'test_rows': meta['split_sizes']['test'], 'calibration_method': meta['calibration_method'],
        'metrics': comparison, 'metric_deltas': {key: comparison[1][key] - comparison[0][key] for key in keys},
        'ranking': [{'rank': index, **row} for index, row in enumerate(ranking, 1)],
        'ranking_basis': meta['ranking_basis'], 'evaluation_note': meta['test_evaluation_note'],
        'calibration': {'bins': bins, 'development_selection': calibration['development_selection'],
                        'selection_basis': calibration['selection_basis']},
        'shap': {'interpretation': meta['shap_interpretation'], 'importance': shap, 'top_features': shap[:20]},
    }


def load_dashboard() -> dict:
    """Read only the current run's saved metadata and reports for the admin dashboard."""
    try:
        lite_id = _run_id(LITE_ROOT / 'artifacts/lite/latest.json', r'\d{8}T\d{6}Z-[a-f0-9]{8}')
        research_id = _run_id(RESEARCH_ROOT / 'latest.json', r'\d{8}T\d{6}Z')
        lite_meta = _json(LITE_ROOT / f'artifacts/lite/runs/{lite_id}/metadata.json')
        research_dir = RESEARCH_ROOT / research_id
        research_meta = _json(research_dir / 'metadata.json')
        research_run = _json(research_dir / 'model_comparison.json')
        calibration = _json(research_dir / 'calibration_results.json')
        if lite_meta.get('run_id') != lite_id or research_meta.get('run_id') != research_id:
            raise ValueError('Artifact metadata does not match the latest run pointer')
        if research_meta.get('contract') != 'FULL_RESEARCH_V1_NO_EXT':
            raise ValueError('Unexpected research feature contract')

        paired = research_meta['test_metrics']
        metric_sources = {
            'roc_auc': ('roc_auc', 'roc_auc'),
            'average_precision': ('average_precision', 'average_precision'),
            'brier_score': ('brier_score', 'brier_score'),
        }
        lite_metrics, research_metrics, deltas = {}, {}, {}
        for metric, (lite_key, research_key) in metric_sources.items():
            lite_value = float(paired['Lite'][lite_key])
            research_value = float(paired['FULL_RESEARCH_V1_NO_EXT'][research_key])
            lite_metrics[metric] = lite_value
            research_metrics[metric] = research_value
            deltas[metric] = research_value - lite_value

        lite_features = lite_meta['feature_columns']
        research_features = research_meta['feature_columns']
        if len(lite_features) != 17 or len(research_features) != 22:
            raise ValueError('Model feature count does not match the published contracts')
        shap = _csv(research_dir / 'shap_feature_importance.csv')
        top_20 = _csv(research_dir / 'top_20_features.csv')
        ablation = _csv(research_dir / 'feature_ablation_summary.csv')
        shap_rows = [{'feature': row['feature'], 'mean_abs_shap_raw_margin': float(row['mean_abs_shap_raw_margin'])}
                     for row in shap]
        top_rows = [{'feature': row['feature'], 'mean_abs_shap_raw_margin': float(row['mean_abs_shap_raw_margin'])}
                    for row in top_20]
        ablation_rows = [{
            'variant': row['variant'], 'feature_count': int(row['feature_count']),
            'roc_auc': float(row['roc_auc']), 'average_precision': float(row['average_precision']),
            'brier_score': float(row['brier_score']), 'evaluation_cohort': row['evaluation_cohort'],
        } for row in ablation]

        bins = []
        for model in ('Lite', 'FULL_RESEARCH_V1_NO_EXT'):
            for index, row in enumerate(calibration[model], start=1):
                bins.append({
                    'model': model, 'bin': index,
                    'mean_predicted_probability': float(row['mean_predicted_probability']),
                    'observed_default_rate': float(row['observed_default_rate']),
                })
        split_size = sum(int(value) for value in research_meta['split_sizes'].values())
        calibration_method = research_meta.get('calibration_method', 'Not recorded')
        xgboost = _xgboost_benchmark(research_meta)
        return {
            'mode': 'RESEARCH_ONLY', 'release_ready': False,
            'metrics': [
                {'name': 'Lite', 'model': 'LightGBM', 'status': 'Current application baseline · research mode',
                 'run_id': lite_id, 'feature_count': len(lite_features), 'values': lite_metrics},
                {'name': 'FULL_RESEARCH_V1_NO_EXT', 'model': 'LightGBM', 'status': 'Research candidate · RESEARCH_ONLY',
                 'run_id': research_id, 'feature_count': len(research_features), 'values': research_metrics},
            ],
            'metric_deltas': deltas,
            'calibration': {
                'method': calibration_method, 'cohort': calibration.get('cohort', paired.get('evaluation', '')),
                'test_rows': int(paired['test_rows']), 'bins': bins,
                'summary': f'Both models use {calibration_method} calibration. The curves show saved probabilities versus observed outcome rates across 10 bins on the shared test cohort, which has already been inspected in earlier research.',
            },
            'shap': {
                'interpretation': research_meta.get('shap_interpretation', ''),
                'top_features': top_rows, 'importance': shap_rows,
            },
            'contracts': {
                'Lite': {'feature_count': len(lite_features), 'groups': _group_features(lite_features)},
                'FULL_RESEARCH_V1_NO_EXT': {'feature_count': len(research_features),
                                            'groups': _group_features(research_features)},
            },
            'ablation': ablation_rows,
            'registry': [
                {'name': 'Lite', 'version': lite_id, 'feature_count': len(lite_features),
                 'training_date': lite_meta.get('trained_at', lite_id[:8]),
                 'calibration_method': lite_meta.get('calibration_method', 'Not recorded'),
                 'dataset_size': sum(int(value) for value in lite_meta['split_sizes'].values()),
                 'status': 'Current application baseline · research mode'},
                {'name': 'FULL_RESEARCH_V1_NO_EXT', 'version': research_id,
                 'feature_count': len(research_features), 'training_date': research_id[:8],
                 'calibration_method': calibration_method, 'dataset_size': split_size,
                 'status': 'Research candidate · RESEARCH_ONLY'},
                *([{'name': 'XGBoost · FULL_RESEARCH_V1_NO_EXT', 'version': xgboost['run_id'],
                    'feature_count': 22, 'training_date': xgboost['run_id'][:8],
                    'calibration_method': xgboost['calibration_method'], 'dataset_size': split_size,
                    'status': 'Research benchmark · RESEARCH_ONLY'}] if xgboost else []),
            ],
            'xgboost_benchmark': xgboost,
            'limitations': LIMITATIONS + ['The shared test cohort has been inspected in previous experiments; subsequent comparisons are reused-holdout research, not independent confirmation.'],
            'ablation_note': 'Research diagnostics only. Ablations use the reserved policy partition and are not final-test comparisons.',
            'shap_note': 'Existing Tree SHAP outputs only; no SHAP values are computed by this dashboard.',
        }
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError, csv.Error) as exc:
        raise HTTPException(503, 'Model research artifacts are unavailable or inconsistent') from exc
