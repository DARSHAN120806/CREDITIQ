import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from creditiq_ml import config as C
from make_synthetic import generate


@pytest.fixture
def data_root(tmp_path, monkeypatch):
    raw = generate(tmp_path / "raw", n=600, n_test=40)
    monkeypatch.setattr(C, "RAW_DIR", raw)
    monkeypatch.setattr(C, "PROCESSED_DIR", tmp_path / "processed")
    monkeypatch.setattr(C, "ARTIFACTS_DIR", tmp_path / "artifacts")
    monkeypatch.setattr(C, "REPORTS_DIR", tmp_path / "reports")
    return raw


@pytest.fixture
def applicant():
    return {"age_years": 40., "years_employed": 10., "annual_income": 120000.,
            "requested_amount": 240000., "quoted_monthly_payment": 5000.,
            "household_size": 3, "dependent_children": 1, "employment_type": "WORKING",
            "education_level": "HIGHER"}
