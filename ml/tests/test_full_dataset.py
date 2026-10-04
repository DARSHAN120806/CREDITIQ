"""Dataset construction tests only: never fit or modify a model."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pandas as pd
import pytest

from creditiq_ml import config as C
from creditiq_ml.contracts import FULL_FEATURES, ContractError
from creditiq_ml.features import build_feature_table
from creditiq_ml.provenance import sha256

spec = importlib.util.spec_from_file_location("full_dataset_tool", Path(__file__).parents[1] / "tools/full_dataset.py")
tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)


def test_full_build_matches_existing_contract_without_test_cohort(data_root, tmp_path):
    expected = build_feature_table(feature_set="full", use_cache=False)
    expected = expected[expected.IS_TRAIN.eq(1)].sort_values("SK_ID_CURR").reset_index(drop=True)
    result = tool.build(data_root, tmp_path / "out", chunksize=119)
    actual = pd.read_parquet(tmp_path / "out/full_features.parquet")
    pd.testing.assert_frame_equal(actual, expected, check_dtype=False)
    assert result["training_ready"] and result["generated_features"] == 60
    assert result["eligible_rows"] == 600 and not result["competition_test_included"]
    assert "application_test.csv" not in result["input_sha256"]


def test_missing_history_evidence_never_fabricates_features(data_root, tmp_path):
    path = data_root / "adapter_manifest.json"
    manifest = json.loads(path.read_text())
    manifest["availability_verified"] = False
    path.write_text(json.dumps(manifest))
    before = sha256(path)
    result = tool.build(data_root, tmp_path / "blocked")
    assert result["status"] == "BLOCKED" and not result["training_ready"]
    assert result["generated_features"] == 17 and len(result["unavailable_features"]) == 43
    assert not (tmp_path / "blocked/full_features.parquet").exists()
    quality = pd.read_csv(tmp_path / "blocked/feature_quality.csv")
    assert len(quality) == len(FULL_FEATURES)
    assert quality[quality.status.eq("BLOCKED_NOT_GENERATED")].coverage_pct.eq(0).all()
    assert sha256(path) == before


def test_reproducible_output_and_restore_configuration(data_root, tmp_path):
    original = C.RAW_DIR
    one = tool.build(data_root, tmp_path / "one", 100)
    two = tool.build(data_root, tmp_path / "two", 250)
    assert one["dataset_sha256"] == two["dataset_sha256"]
    assert one["input_sha256"] == two["input_sha256"]
    assert C.RAW_DIR == original
    pd.testing.assert_frame_equal(pd.read_csv(tmp_path / "one/source_coverage.csv"), pd.read_csv(tmp_path / "two/source_coverage.csv"))


def test_missing_schedule_blocks_not_inferred_from_payment_rows(data_root, tmp_path):
    (data_root / "installment_schedule.csv").unlink()
    result = tool.build(data_root, tmp_path / "out")
    assert not result["training_ready"]
    assert any("installment_schedule" in b for b in result["blockers"])


def test_existing_output_and_raw_directory_rejected(data_root, tmp_path):
    with pytest.raises(ValueError, match="separate"):
        tool.build(data_root, data_root)
    out = tmp_path / "existing"
    out.mkdir()
    (out / "important.txt").write_text("preserve")
    with pytest.raises(ValueError, match="empty"):
        tool.build(data_root, out)
    assert (out / "important.txt").read_text() == "preserve"


def test_future_payments_are_filtered_by_existing_aggregation(data_root, tmp_path):
    path = data_root / "installments_payments.csv"
    p = pd.read_csv(path)
    p["DAYS_AVAILABLE"] = 1
    p.to_csv(path, index=False)
    result = tool.build(data_root, tmp_path / "out")
    assert result["training_ready"]
    frame = pd.read_parquet(tmp_path / "out/full_features.parquet")
    assert frame.installment_fully_paid_count.eq(0).all()
    assert frame.installment_unpaid_overdue_count.eq(3).all()


def test_relational_violation_blocks_publication(data_root, tmp_path):
    path = data_root / "POS_CASH_balance.csv"
    data = pd.read_csv(path)
    data.loc[0, "SK_ID_CURR"] = 999999
    data.to_csv(path, index=False)
    result = tool.build(data_root, tmp_path / "out")
    assert not result["training_ready"]
    assert any("owner" in b for b in result["blockers"])
    assert not (tmp_path / "out/full_features.parquet").exists()


def test_invalid_target_rejected(data_root, tmp_path):
    path = data_root / "application_train.csv"
    data = pd.read_csv(path)
    data.loc[0, "TARGET"] = 5
    data.to_csv(path, index=False)
    with pytest.raises(ContractError, match="TARGET"):
        tool.build(data_root, tmp_path / "out")


def test_cli_blocked_exit_code_and_reports(data_root, tmp_path):
    (data_root / "installment_schedule.csv").unlink()
    result = subprocess.run([sys.executable, str(Path(tool.__file__)), "--raw-dir", str(data_root),
                             "--output-dir", str(tmp_path / "cli")], capture_output=True, text=True)
    assert result.returncode == 2, result.stdout + result.stderr
    assert "BLOCKED: 17/60" in result.stdout
    assert (tmp_path / "cli/FULL_FEATURE_REPORT.md").exists()
