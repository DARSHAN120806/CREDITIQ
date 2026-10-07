"""Build a private, allowlisted runtime artifact bundle. Never copy .env/raw data/backups."""
import hashlib
import json
from pathlib import Path
import re
import shutil

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / '.deployment-assets'


def build():
    if OUT.exists():
        raise SystemExit('Bundle already exists; review/archive it before building another')
    files = []
    lite = ROOT / 'ml/real_data_output/artifacts/lite'
    run = lite / 'runs/20261002T140817Z-045430a7'
    metadata = json.loads((run / 'metadata.json').read_text())
    files.extend([lite / 'latest.json', run / 'metadata.json'])
    for name, expected in metadata['artifact_sha256'].items():
        if Path(name).name != name:
            raise ValueError('Unsafe artifact name')
        path = run / name
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError('Pinned artifact checksum mismatch')
        files.append(path)
    groups = {
        'full_research_v1_no_ext': ['metadata.json', 'model_comparison.json', 'calibration_results.json', 'shap_feature_importance.csv', 'top_20_features.csv', 'feature_ablation_summary.csv'],
        'xgboost_full_research_v1_no_ext': ['metadata.json', 'model_comparison.csv', 'calibration_results.json', 'shap_feature_importance.csv'],
        'customer_segmentation': ['cluster_metrics.json', 'segmentation_model.joblib', 'cluster_summary.csv', 'pca_visualization_data.csv', 'cluster_assignments.parquet', 'SEGMENTATION_REPORT.md'],
    }
    for group, names in groups.items():
        root = ROOT / 'ml/research_output' / group
        run_id = json.loads((root / 'latest.json').read_text())['run_id']
        if not re.fullmatch(r'[A-Za-z0-9_-]+', run_id):
            raise ValueError('Unsafe run ID')
        files.extend([root / 'latest.json', *(root / run_id / name for name in names)])
    if not all(p.is_file() and not p.is_symlink() for p in files):
        raise ValueError('Missing or symlinked artifact')
    manifest = {}
    for source in files:
        relative = source.relative_to(ROOT)
        target = OUT / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        manifest[relative.as_posix()] = hashlib.sha256(target.read_bytes()).hexdigest()
    (OUT / 'manifest.json').write_text(json.dumps(manifest, indent=2))
    print(f'Packaged {len(files)} verified/allowlisted runtime files. Keep the bundle and image private.')


if __name__ == '__main__':
    build()
