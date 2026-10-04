import numpy as np
import pandas as pd
import pytest
from creditiq_ml.contracts import ContractError
from creditiq_ml.features import installments_features, previous_features, credit_card_features


def fixture():
    base = {"SK_ID_CURR": 1, "SK_ID_PREV": 10, "NUM_INSTALMENT_NUMBER": 1,
            "NUM_INSTALMENT_VERSION": 1, "DAYS_INSTALMENT": -10, "AMT_INSTALMENT": 100.}
    schedule = pd.DataFrame([{**base, "DAYS_AVAILABLE": -100},
        {**base, "NUM_INSTALMENT_NUMBER": 2, "DAYS_INSTALMENT": -5, "DAYS_AVAILABLE": -100},
        {**base, "NUM_INSTALMENT_NUMBER": 3, "DAYS_INSTALMENT": 10, "DAYS_AVAILABLE": -100}])
    payments = pd.DataFrame([{**base, "PAYMENT_ID": "a", "AMT_PAYMENT": 50., "DAYS_ENTRY_PAYMENT": -12, "DAYS_AVAILABLE": -12},
                             {**base, "PAYMENT_ID": "b", "AMT_PAYMENT": 50., "DAYS_ENTRY_PAYMENT": -8, "DAYS_AVAILABLE": -8}])
    return payments, schedule


def test_partial_payments_and_unpaid_schedule():
    p, s = fixture()
    row = installments_features(p, s).iloc[0]
    assert row.installment_due_count == 2  # Future due item excluded.
    assert row.installment_fully_paid_count == 1
    assert row.installment_late_count == 2
    assert row.installment_unpaid_overdue_count == 1
    assert row.installment_mean_signed_delay == 2
    assert row.installment_mean_overdue_days == 3.5
    assert row.installment_mean_paid_ratio == .5


def test_future_payment_and_availability_do_not_leak():
    p, s = fixture()
    p.loc[1, "DAYS_AVAILABLE"] = 1
    row = installments_features(p, s).iloc[0]
    assert row.installment_fully_paid_count == 0
    assert row.installment_mean_paid_ratio == .25
    assert np.isnan(row.installment_mean_signed_delay)


def test_duplicate_payment_identity_and_schedule_conflicts():
    p, s = fixture()
    duplicated = pd.concat([p, p.iloc[[0]]], ignore_index=True)
    pd.testing.assert_frame_equal(installments_features(p, s), installments_features(duplicated, s))
    duplicated.loc[2, "AMT_PAYMENT"] = 1
    with pytest.raises(ContractError, match="Conflicting duplicate"):
        installments_features(duplicated, s)
    ambiguous = pd.concat([s, s.iloc[[0]].assign(NUM_INSTALMENT_VERSION=2)], ignore_index=True)
    with pytest.raises(ContractError, match="Ambiguous"):
        installments_features(p, ambiguous)


def test_early_completion_and_two_late_parts_count_once():
    p, s = fixture()
    p["DAYS_ENTRY_PAYMENT"] = [-9, -8]
    p["DAYS_AVAILABLE"] = [-9, -8]
    row = installments_features(p, s.iloc[[0]]).iloc[0]
    assert row.installment_late_count == 1
    p["DAYS_ENTRY_PAYMENT"] = [-13, -12]
    p["DAYS_AVAILABLE"] = [-13, -12]
    row = installments_features(p, s.iloc[[0]]).iloc[0]
    assert row.installment_late_count == 0 and row.installment_mean_signed_delay == -2


def test_previous_applications_are_not_booked_loans():
    df = pd.DataFrame({"SK_ID_CURR": [1] * 4, "SK_ID_PREV": [1, 2, 3, 4], "DAYS_DECISION": [-400, -100, -1, 1],
                       "DAYS_AVAILABLE": [-400, -100, -1, -1], "NAME_CONTRACT_STATUS": ["Approved", "Refused", "Canceled", "Approved"]})
    row = previous_features(df).iloc[0]
    assert row.previous_application_count == 3 and row.previous_approved_count == 1
    assert row.previous_refused_count == 1 and row.previous_applications_365d == 2


def test_card_current_weighted_utilization_and_missing_limit():
    df = pd.DataFrame({"SK_ID_CURR": [1, 1, 1], "SK_ID_PREV": [1, 1, 2], "MONTHS_BALANCE": [-2, -1, -1],
        "DAYS_AVAILABLE": [-60, -30, -30], "SK_DPD": [0, 0, 0], "NAME_CONTRACT_STATUS": ["Active"] * 3,
        "AMT_BALANCE": [90., 50., 300.], "AMT_CREDIT_LIMIT_ACTUAL": [100., 100., 900.]})
    row = credit_card_features(df).iloc[0]
    assert row.card_current_utilization == .35
    assert row.card_historical_mean_utilization == pytest.approx((.9 + .5 + 1/3) / 3)
    df.loc[2, "AMT_CREDIT_LIMIT_ACTUAL"] = np.nan
    assert np.isnan(credit_card_features(df).card_current_utilization.iloc[0])
