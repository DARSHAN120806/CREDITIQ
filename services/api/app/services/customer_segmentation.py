"""Read-only admin view of saved research segmentation outputs."""
import csv
import json
import re
from pathlib import Path

from fastapi import HTTPException

ROOT = Path(__file__).resolve().parents[4]
SEGMENTATION_ROOT = ROOT / 'ml/research_output/customer_segmentation'
LIMITATIONS = [
    'Exploratory groups only: cluster IDs are arbitrary and are not risk, quality, eligibility, or lending labels.',
    'The source is a historical Home Credit cohort and may not represent CreditIQ users.',
    'The source contract has no credit utilization feature; requested principal is only a current-loan amount proxy, not total debt.',
    'Bureau inquiry history availability for real applicants remains unresolved.',
    'K-Means uses Euclidean distance and is sensitive to outliers, scaling, encoding, and the requested cluster count.',
    'PCA is a lossy two-dimensional view; visual separation does not validate cluster quality.',
    'TARGET was excluded from clustering, selection, profiling, and descriptions.',
]


def load_dashboard() -> dict:
    try:
        run_id = json.loads((SEGMENTATION_ROOT / 'latest.json').read_text(encoding='utf-8'))['run_id']
        if not re.fullmatch(r'\d{8}T\d{6}Z', run_id):
            raise ValueError('Invalid segmentation run pointer')
        run = SEGMENTATION_ROOT / run_id
        metrics = json.loads((run / 'cluster_metrics.json').read_text(encoding='utf-8'))
        if metrics.get('mode') != 'RESEARCH_ONLY' or metrics.get('release_ready') is not False:
            raise ValueError('Segmentation output is not marked research-only')
        if metrics.get('model_sha256') is None or not (run / 'segmentation_model.joblib').is_file():
            raise ValueError('Segmentation model artifact is missing')
        with (run / 'cluster_summary.csv').open(encoding='utf-8-sig', newline='') as file:
            profiles = list(csv.DictReader(file))
        with (run / 'pca_visualization_data.csv').open(encoding='utf-8-sig', newline='') as file:
            pca = [{key: (int(value) if key == 'cluster_id' else float(value))
                    for key, value in row.items()} for row in csv.DictReader(file)]
        required = ('cluster_assignments.parquet', 'SEGMENTATION_REPORT.md')
        if any(not (run / name).is_file() for name in required) or not profiles or not pca:
            raise ValueError('A required segmentation output is missing')
        numeric_fields = [key for key in profiles[0] if key not in {'description', 'debt_definition', 'mean_credit_utilization'}]
        for row in profiles:
            for key in numeric_fields:
                row[key] = float(row[key]) if key not in {'cluster_id', 'cluster_size'} else int(row[key])
            row['mean_credit_utilization'] = float(row['mean_credit_utilization']) if row.get('mean_credit_utilization') else None
        return {
            'mode': 'RESEARCH_ONLY', 'release_ready': False, 'run_id': run_id,
            'methodology': metrics['selection_criteria'], 'source': {
                'contract': metrics['source_contract'], 'run_id': metrics['source_run_id'],
                'rows': metrics['source_rows'], 'feature_count': metrics['feature_count'],
            },
            'selected_k': metrics['selected_k'], 'selection_metrics': metrics['selection'],
            'final_model': metrics['final_model'], 'profiles': profiles,
            'pca': {'explained_variance_ratio': metrics['pca']['explained_variance_ratio'], 'points': pca},
            'limitations': LIMITATIONS,
        }
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError, csv.Error) as exc:
        raise HTTPException(503, 'Customer segmentation artifacts are unavailable or inconsistent') from exc
