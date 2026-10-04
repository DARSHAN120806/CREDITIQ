"""Research-only K-Means segmentation from the pinned FULL_RESEARCH_V1_NO_EXT dataset."""
from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.cluster import KMeans
from sklearn.compose import ColumnTransformer
from sklearn.decomposition import PCA
from sklearn.impute import SimpleImputer
from sklearn.metrics import davies_bouldin_score, silhouette_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

ROOT = Path(__file__).resolve().parents[2]
RESEARCH_ROOT = ROOT / 'ml/research_output/full_research_v1_no_ext'
OUTPUT_ROOT = ROOT / 'ml/research_output/customer_segmentation'
SEED = 42
FIT_SAMPLE_SIZE = 20_000
METRIC_SAMPLE_SIZE = 5_000
PCA_SAMPLE_SIZE = 8_000
MIN_CLUSTER_SHARE = 0.01
SILHOUETTE_TOLERANCE = 0.01

PROFILE_NUMERIC = {
    'mean_income_annual': 'annual_income',
    'mean_debt_requested_amount': 'requested_amount',
    'mean_inquiries_1m': 'credit_bureau_inquiries_1m',
    'mean_inquiries_3m': 'credit_bureau_inquiries_3m',
    'mean_inquiries_12m': 'credit_bureau_inquiries_12m',
    'mean_payment_income_ratio': 'proposed_payment_income_ratio',
    'mean_principal_income_ratio': 'principal_income_ratio',
    'mean_payment_principal_ratio': 'payment_principal_ratio',
    'mean_loan_to_goods_price_ratio': 'loan_to_goods_price_ratio',
    'mean_age_years': 'age_years',
    'mean_employment_years': 'years_employed',
}


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding='utf-8'))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def source_dataset() -> tuple[pd.DataFrame, list[str], str, Path]:
    run_id = read_json(RESEARCH_ROOT / 'latest.json')['run_id']
    source_dir = RESEARCH_ROOT / run_id
    metadata = read_json(source_dir / 'metadata.json')
    if metadata.get('contract') != 'FULL_RESEARCH_V1_NO_EXT' or metadata.get('run_id') != run_id:
        raise ValueError('Latest research metadata is inconsistent')
    features = metadata['feature_columns']
    path = source_dir / 'full_research_v1_no_ext_train.parquet'
    frame = pd.read_parquet(path)
    if set(features) - set(frame.columns) or not {'SK_ID_CURR', 'TARGET'} <= set(frame.columns):
        raise ValueError('Training dataset does not match the research contract')
    # TARGET and applicant ID are deliberately excluded from all clustering inputs.
    return frame, features, run_id, path


def preprocessing(features: list[str], frame: pd.DataFrame) -> Pipeline:
    categorical = [name for name in features if not pd.api.types.is_numeric_dtype(frame[name].dtype)]
    numeric = [name for name in features if name not in categorical]
    encoded = ColumnTransformer([
        ('numeric', SimpleImputer(strategy='median', keep_empty_features=True), numeric),
        ('categorical', Pipeline([
            ('impute', SimpleImputer(strategy='most_frequent', keep_empty_features=True)),
            ('one_hot', OneHotEncoder(handle_unknown='ignore', sparse_output=False, dtype=np.float32)),
        ]), categorical),
    ], remainder='drop')
    return Pipeline([('encode_impute', encoded), ('standardize', StandardScaler())])


def evaluate_k(matrix: np.ndarray) -> tuple[list[dict], int]:
    rng = np.random.default_rng(SEED)
    selected = rng.permutation(len(matrix))[:min(FIT_SAMPLE_SIZE, len(matrix))]
    fit_data = matrix[selected]
    metric_data = fit_data[:min(METRIC_SAMPLE_SIZE, len(fit_data))]
    rows = []
    for k in range(2, 11):
        model = KMeans(n_clusters=k, n_init=5, max_iter=150, random_state=SEED, algorithm='lloyd')
        model.fit(fit_data)
        labels = model.predict(metric_data)
        shares = np.bincount(labels, minlength=k) / len(labels)
        rows.append({
            'k': k,
            'silhouette_score': float(silhouette_score(metric_data, labels)),
            'davies_bouldin_index': float(davies_bouldin_score(metric_data, labels)),
            'inertia': float(model.inertia_),
            'minimum_cluster_share': float(shares.min()),
            'eligible_by_minimum_share': bool(shares.min() >= MIN_CLUSTER_SHARE),
        })
    eligible = [row for row in rows if row['eligible_by_minimum_share']]
    if not eligible:
        raise RuntimeError('No K from 2 to 10 produced clusters of at least 1% on the diagnostic sample')
    best_silhouette = max(row['silhouette_score'] for row in eligible)
    shortlist = [row for row in eligible if row['silhouette_score'] >= best_silhouette - SILHOUETTE_TOLERANCE]
    chosen = min(shortlist, key=lambda row: (row['davies_bouldin_index'], row['k']))
    return rows, int(chosen['k'])


def describe_cluster(profile: dict, cohort: dict) -> str:
    traits = []
    for key, label in (
        ('mean_income_annual', 'income'),
        ('mean_debt_requested_amount', 'requested loan amount'),
    ):
        value, average = profile[key], cohort[key]
        if average and value >= average * 1.15:
            traits.append(f'higher-than-cohort-average {label}')
        elif average and value <= average * 0.85:
            traits.append(f'lower-than-cohort-average {label}')
    for key, label, margin in (
        ('mean_age_years', 'age', 4),
        ('mean_employment_years', 'employment tenure', 2),
    ):
        value, average = profile[key], cohort[key]
        if value >= average + margin:
            traits.append(f'higher average {label}')
        elif value <= average - margin:
            traits.append(f'lower average {label}')
    cluster_inquiries = sum(profile[key] for key in ('mean_inquiries_1m', 'mean_inquiries_3m', 'mean_inquiries_12m'))
    cohort_inquiries = sum(cohort[key] for key in ('mean_inquiries_1m', 'mean_inquiries_3m', 'mean_inquiries_12m'))
    if cluster_inquiries > cohort_inquiries + 0.25:
        traits.append('more recorded inquiry activity')
    elif cluster_inquiries + 0.25 < cohort_inquiries:
        traits.append('less recorded inquiry activity')
    return 'This segment has ' + ', '.join(traits) + '.' if traits else 'This segment is near cohort averages across the profiled measures.'


def build_profiles(frame: pd.DataFrame, labels: np.ndarray) -> tuple[pd.DataFrame, list[dict]]:
    cohort = {key: float(frame[column].mean()) for key, column in PROFILE_NUMERIC.items()}
    rows = []
    descriptions = []
    total = len(frame)
    for cluster in sorted(np.unique(labels)):
        subset = frame.loc[labels == cluster]
        row = {
            'cluster_id': int(cluster) + 1,
            'cluster_size': len(subset),
            'cluster_percentage': len(subset) * 100 / total,
            **{key: float(subset[column].mean()) for key, column in PROFILE_NUMERIC.items()},
            # The 22-feature research contract contains no credit utilization field.
            'mean_credit_utilization': None,
        }
        row['description'] = describe_cluster(row, cohort)
        row['debt_definition'] = 'requested_amount (application principal), not total existing liabilities'
        rows.append(row)
        descriptions.append({'cluster_id': row['cluster_id'], 'description': row['description']})
    return pd.DataFrame(rows), descriptions


def write_report(path: Path, run_id: str, source_hash: str, feature_count: int,
                 row_count: int, selection: list[dict], selected_k: int,
                 profiles: pd.DataFrame, pipeline: Pipeline) -> None:
    metrics_table = '| K | Silhouette | Davies-Bouldin | Inertia | Min cluster share | Eligible |\n|---:|---:|---:|---:|---:|:---:|\n'
    metrics_table += ''.join(
        f"| {row['k']} | {row['silhouette_score']:.4f} | {row['davies_bouldin_index']:.4f} | "
        f"{row['inertia']:.2f} | {row['minimum_cluster_share']:.2%} | {'Yes' if row['eligible_by_minimum_share'] else 'No'} |\n"
        for row in selection)
    profile_table = '| Segment | Size | Share | Mean income | Mean requested amount | Description |\n|---|---:|---:|---:|---:|---|\n'
    profile_table += ''.join(
        f"| Segment {int(row.cluster_id)} | {int(row.cluster_size):,} | {row.cluster_percentage:.2f}% | "
        f"{row.mean_income_annual:,.0f} | {row.mean_debt_requested_amount:,.0f} | {row.description} |\n"
        for row in profiles.itertuples())
    path.write_text(f"""# Customer Segmentation Research Report

**Status:** RESEARCH_ONLY · `release_ready=false` · descriptive segmentation, not for lending decisions.

## Source and method

- Source contract: `FULL_RESEARCH_V1_NO_EXT`, run `{run_id}`; source rows: {row_count:,}; applicant-level source SHA-256: `{source_hash}`.
- Clustering uses the 22 contracted feature fields. `SK_ID_CURR` is retained only in the assignment output; `TARGET` is excluded from preprocessing, K selection, fitting, profiles, and descriptions.
- Numeric missing values use training-source medians; categoricals use most-frequent imputation and one-hot encoding. A fitted `StandardScaler` scales the complete encoded feature matrix.
- Candidate K-Means uses a reproducible random sample of up to {FIT_SAMPLE_SIZE:,} rows (seed {SEED}), `n_init=5`, and `max_iter=150`. Silhouette and Davies-Bouldin are computed on the same first {METRIC_SAMPLE_SIZE:,} rows from that sample; inertia is measured on the full candidate fitting sample.
- Final model uses K-Means with `n_init=10`, `max_iter=300`, and seed {SEED}, fitted on all {row_count:,} records after the selected K.

## K selection criteria

Only candidates with at least {MIN_CLUSTER_SHARE:.0%} of metric-sample records in every cluster are eligible. Find the best eligible silhouette score; retain candidates within {SILHOUETTE_TOLERANCE:.2f} of that maximum, then choose the lowest Davies-Bouldin Index, with smaller K as the final tie-break. Inertia is reported as a compactness diagnostic and is not minimized by itself because it decreases as K grows. Selected K: **{selected_k}**.

{metrics_table}
## Cluster profiles

Mean debt is defined as requested application principal (`requested_amount`); it is not total existing debt. The contract has no credit-card utilization field, so utilization is unavailable and is left blank. Cluster descriptions compare observed means to cohort means and have neutral descriptive names only.

{profile_table}
## Limitations

- These are exploratory groups, not risk classes, customer quality labels, recommendations, or lending decisions.
- The research contract intentionally excludes verified bureau/account history; inquiry fields have unresolved real-applicant availability.
- No utilization measure exists in this contract. Do not reinterpret payment-to-income ratios as credit utilization.
- One-hot encoded categories and standardized numeric values determine Euclidean distance; K-Means assumes roughly spherical groups and is sensitive to outliers and preprocessing choices.
- The selected K has a modest silhouette score ({next(row['silhouette_score'] for row in selection if row['k'] == selected_k):.4f}); segment separation is weak, so boundaries should be treated cautiously.
- PCA is a two-dimensional visualization projection only; apparent separation in the plot does not validate segment quality.
- The historical Home Credit population and TARGET horizon are not independently verified; these clusters may not represent CreditIQ users.
- No prediction model was trained, changed, or invoked. Cluster IDs are arbitrary and can permute across independently rebuilt versions.

## Artifacts

- `segmentation_model.joblib` — fitted preprocessing, scaler, and final K-Means pipeline.
- `cluster_assignments.parquet` — applicant ID and neutral cluster ID; no TARGET or risk label.
- `cluster_summary.csv`, `cluster_metrics.json`, `pca_visualization_data.csv`.
""", encoding='utf-8')


def run() -> Path:
    frame, features, source_run, source_path = source_dataset()
    source_hash = sha256(source_path)
    x = frame[features].copy()
    prep = preprocessing(features, frame)
    encoded = prep.fit_transform(x)
    scaled = StandardScaler().fit_transform(encoded)
    selection, selected_k = evaluate_k(scaled)

    pipeline = Pipeline([
        ('encode_impute', prep),
        ('standardize', StandardScaler()),
        ('kmeans', KMeans(n_clusters=selected_k, n_init=10, max_iter=300,
                          random_state=SEED, algorithm='lloyd')),
    ])
    pipeline.fit(x)
    labels = pipeline.named_steps['kmeans'].labels_
    profiles, descriptions = build_profiles(frame, labels)

    run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    output = OUTPUT_ROOT / run_id
    output.mkdir(parents=True, exist_ok=False)
    pd.DataFrame({'SK_ID_CURR': frame['SK_ID_CURR'].to_numpy(),
                  'cluster_id': labels.astype(np.int16) + 1}).to_parquet(
                      output / 'cluster_assignments.parquet', index=False)
    profiles.to_csv(output / 'cluster_summary.csv', index=False, quoting=csv.QUOTE_MINIMAL)
    rng = np.random.default_rng(SEED)
    pca_indices = np.sort(rng.choice(len(frame), size=min(PCA_SAMPLE_SIZE, len(frame)), replace=False))
    pca = PCA(n_components=2, svd_solver='randomized', random_state=SEED)
    pca_values = pca.fit_transform(scaled[pca_indices])
    pd.DataFrame({'pca_1': pca_values[:, 0], 'pca_2': pca_values[:, 1],
                  'cluster_id': labels[pca_indices].astype(np.int16) + 1}).to_csv(
                      output / 'pca_visualization_data.csv', index=False)

    evaluation_info = {
        'source_contract': 'FULL_RESEARCH_V1_NO_EXT', 'source_run_id': source_run,
        'source_dataset': str(source_path.relative_to(ROOT)).replace('\\', '/'),
        'source_sha256': source_hash, 'source_rows': len(frame), 'feature_count': len(features),
        'features': features, 'excluded_fields': ['SK_ID_CURR (identifier only)', 'TARGET (excluded to prevent outcome leakage)'],
        'categorical_features': [name for name in features if not pd.api.types.is_numeric_dtype(frame[name].dtype)],
        'numeric_features': [name for name in features if pd.api.types.is_numeric_dtype(frame[name].dtype)],
        'preprocessing': 'numeric median imputation; categorical most-frequent imputation and dense one-hot encoding; StandardScaler',
        'selection': selection, 'selected_k': selected_k,
        'selection_criteria': {
            'k_evaluated': list(range(2, 11)), 'minimum_cluster_share': MIN_CLUSTER_SHARE,
            'silhouette_tolerance': SILHOUETTE_TOLERANCE,
            'rule': 'Filter by minimum cluster share; shortlist within 0.01 of maximum silhouette; minimize Davies-Bouldin Index; tie-break on lower K. Inertia is diagnostic only.',
            'fit_sample_size': min(FIT_SAMPLE_SIZE, len(frame)), 'metric_sample_size': min(METRIC_SAMPLE_SIZE, FIT_SAMPLE_SIZE),
            'inertia_basis': 'candidate K-Means fit sample',
        },
        'final_model': {'algorithm': 'KMeans', 'n_clusters': selected_k, 'n_init': 10,
                        'max_iter': 300, 'random_state': SEED},
        'pca': {'method': 'PCA', 'components': 2, 'visualization_rows': len(pca_indices),
                'explained_variance_ratio': pca.explained_variance_ratio_.tolist(), 'random_state': SEED},
        'profiles': profiles.replace({np.nan: None}).to_dict(orient='records'),
        'cluster_descriptions': descriptions,
        'utilization_available': False,
        'debt_proxy': 'requested_amount is loan principal on the current application, not total debt',
        'mode': 'RESEARCH_ONLY', 'release_ready': False,
        'created_at': datetime.now(timezone.utc).isoformat(),
        'software': {'python': __import__('platform').python_version(), 'pandas': pd.__version__, 'scikit_learn': sklearn.__version__},
    }
    (output / 'cluster_metrics.json').write_text(json.dumps(evaluation_info, indent=2, allow_nan=False), encoding='utf-8')
    joblib.dump(pipeline, output / 'segmentation_model.joblib', compress=3)
    loaded = joblib.load(output / 'segmentation_model.joblib')
    if loaded.named_steps['kmeans'].n_clusters != selected_k or not np.array_equal(
            loaded.predict(x.iloc[:100]), labels[:100]):
        raise RuntimeError('Serialized segmentation pipeline failed its reload/prediction check')
    evaluation_info['model_sha256'] = sha256(output / 'segmentation_model.joblib')
    (output / 'cluster_metrics.json').write_text(json.dumps(evaluation_info, indent=2, allow_nan=False), encoding='utf-8')
    write_report(output / 'SEGMENTATION_REPORT.md', source_run, source_hash, len(features),
                 len(frame), selection, selected_k, profiles, pipeline)
    (OUTPUT_ROOT / 'latest.json').write_text(json.dumps({'run_id': run_id}, indent=2) + '\n', encoding='utf-8')
    return output


if __name__ == '__main__':
    print(run())
