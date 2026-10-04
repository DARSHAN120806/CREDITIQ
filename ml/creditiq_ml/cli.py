"""Usage:  python -m creditiq_ml.cli <eda|features|train|explain|segment|all> [options]"""
import argparse
import logging
from pathlib import Path
from . import config as C


def main():
    ap = argparse.ArgumentParser(prog="creditiq_ml")
    ap.add_argument("stage", choices=["eda", "features", "train", "explain", "segment", "all"])
    ap.add_argument("--feature-set", choices=["full", "lite"], default="lite")
    ap.add_argument("--raw-dir", type=Path, default=C.RAW_DIR)
    ap.add_argument("--output-dir", type=Path, default=None, help="Isolated processed/artifacts/reports root")
    ap.add_argument("--run-id", default=None, help="Immutable run for explain/segment")
    ap.add_argument("--trials", type=int, default=25, help="Optuna trials for XGBoost/LightGBM")
    ap.add_argument("--models", nargs="+", choices=C.MODEL_NAMES, default=None)
    ap.add_argument("--max-rows", type=int, default=None, help="subsample training rows (quick dev runs)")
    ap.add_argument("--tune-rows", type=int, default=C.TUNE_ROWS)
    ap.add_argument("--no-cache", action="store_true", help="rebuild features.parquet")
    a = ap.parse_args()
    if a.trials < 1 or a.tune_rows < 20 or (a.max_rows is not None and a.max_rows < 100):
        ap.error("trials>=1, tune-rows>=20 and max-rows>=100 required")
    if a.stage == "segment" and a.feature_set != "full":
        ap.error("segmentation requires --feature-set full")
    C.RAW_DIR = a.raw_dir.resolve()
    if a.output_dir:
        output = a.output_dir.resolve()
        C.PROCESSED_DIR, C.ARTIFACTS_DIR, C.REPORTS_DIR = output / "processed", output / "artifacts", output / "reports"
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")

    if a.stage == "eda":
        from .eda import run_eda; run_eda()
    if a.stage in ("features", "all"):
        from .features import build_feature_table; build_feature_table(use_cache=not a.no_cache, feature_set=a.feature_set)
    if a.stage in ("train", "all"):
        from .train import train_all
        train_all(a.feature_set, a.trials, a.models, a.max_rows, a.tune_rows, use_cache=not a.no_cache)
    if a.stage in ("explain", "all"):
        from .explain import run_explain; run_explain(a.feature_set, run_id=a.run_id)
    if a.stage in ("segment", "all") and a.feature_set == "full":
        from .segmentation import run_segmentation; run_segmentation(run_id=a.run_id)


if __name__ == "__main__":
    main()
