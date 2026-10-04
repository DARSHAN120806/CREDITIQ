"""Read-only, pinned research artifact integration; no training or artifact writes."""
import hashlib
import importlib.metadata
import json
from pathlib import Path
import sys
import threading

from app.core.config import API_ROOT

ROOT = API_ROOT.parents[1]
ML_ROOT = ROOT / 'ml'
RUN_ID = '20261002T140817Z-045430a7'
RUN = ML_ROOT / 'real_data_output/artifacts/lite/runs' / RUN_ID
# Fixed trusted local code path, never supplied by an HTTP request.
if str(ML_ROOT) not in sys.path:
    sys.path.insert(0, str(ML_ROOT))


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


class LiteModel:
    def __init__(self):
        import joblib
        from creditiq_ml.contracts import LITE_FEATURES
        self.metadata = json.loads((RUN / 'metadata.json').read_text())
        m = self.metadata
        if (m['run_id'] != RUN_ID or m['feature_columns'] != LITE_FEATURES or
                m['schema_version'] != 'lite-v1' or m['currency'] != 'XXX' or
                m['release_ready'] is not False or m['release_status'] != 'RESEARCH_ONLY'):
            raise ValueError('Invalid pinned research release metadata')
        for name, expected in m['artifact_sha256'].items():
            if Path(name).name != name or digest(RUN / name) != expected:
                raise ValueError('Artifact checksum mismatch')
        for name, expected in m['input_manifest']['code'].items():
            if Path(name).name != name or digest(ML_ROOT / 'creditiq_ml' / name) != expected:
                raise ValueError('ML source checksum mismatch')
        for package in ('joblib', 'numpy', 'pandas', 'scikit-learn', 'scipy', 'lightgbm'):
            if importlib.metadata.version(package) != m['runtime']['packages'][package]:
                raise ValueError(f'Artifact runtime mismatch: {package}')
        self.model = joblib.load(RUN / 'best_model.joblib')
        if (self.model.feature_columns != LITE_FEATURES or self.model.meta['run_id'] != RUN_ID
                or self.model.schema_version != 'lite-v1' or self.model.variant != 'lite'
                or self.model.meta['release_ready'] is not False):
            raise ValueError('Artifact/metadata contract mismatch')
        self.model.classifier.set_params(n_jobs=1)
        self.lock = threading.Lock()
        self.policy_json = json.loads((RUN / 'policy.json').read_text())

    def score(self, payload, quote):
        from creditiq_ml.contracts import request_features
        from creditiq_ml.risk import DecisionPolicy
        features = request_features(payload, currency='XXX', quote=quote)
        with self.lock:
            result = self.model.score_request(payload, quote=quote, policy=DecisionPolicy())
            raw = float(self.model.raw_proba(features)[0])
        result['raw_positive_output'] = raw
        # pandas JSON converts missing tenure/derived values to JSON null, never NaN.
        values = json.loads(features.to_json(orient='records', double_precision=15))[0]
        return result, values
