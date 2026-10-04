"""Paths, repeatable training defaults and canonical contract exports."""
from pathlib import Path
from .contracts import LITE_FEATURES, FULL_FEATURES

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed"
ARTIFACTS_DIR = ROOT / "artifacts"
REPORTS_DIR = ROOT / "reports"
SEED = 42
TARGET = "TARGET"
ID_COL = "SK_ID_CURR"
FILES = {
    "application_train": ["application_train.csv"],
    "application_test": ["application_test.csv"],
    "bureau": ["bureau.csv"],
    "bureau_balance": ["bureau_balance.csv"],
    "previous_application": ["previous_application.csv"],
    "installments_payments": ["installments_payments.csv", "instalments_payments.csv"],
    "credit_card_balance": ["credit_card_balance.csv"],
    "pos_cash_balance": ["POS_CASH_balance.csv"],
}
# Continuous PD intervals; the final interval includes 1.0.
RISK_BANDS = [(0, .05, "Low"), (.05, .15, "Medium"), (.15, 1, "High")]
TEST_SIZE = .15
CALIBRATION_SIZE = .15
POLICY_SIZE = .10
DEVELOPMENT_SIZE = .60
TUNE_ROWS = 60000
N_JOBS = 2
MODEL_NAMES = ["logistic_regression", "decision_tree", "random_forest", "xgboost", "lightgbm"]
