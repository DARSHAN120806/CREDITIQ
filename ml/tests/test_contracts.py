import json
import numpy as np
import pandas as pd
import pytest
from creditiq_ml.contracts import (ContractError, lite_features, validate_features,
                                 request_features, LITE_FEATURES, FULL_FEATURES)
from creditiq_ml.features import application_features, build_feature_table


def test_exact_features_and_form_parity(applicant):
    online = lite_features(pd.DataFrame([applicant]))
    source = pd.DataFrame([{"SK_ID_CURR": 1, "NAME_CONTRACT_TYPE": "Cash loans", "DAYS_BIRTH": -40 * 365.25,
                           "DAYS_EMPLOYED": -10 * 365.25, "AMT_INCOME_TOTAL": 120000., "AMT_CREDIT": 240000.,
                           "AMT_ANNUITY": 5000., "CNT_FAM_MEMBERS": 3, "CNT_CHILDREN": 1,
                           "NAME_INCOME_TYPE": "Working", "NAME_EDUCATION_TYPE": "Higher education"}])
    offline = application_features(source)[LITE_FEATURES]
    pd.testing.assert_frame_equal(offline, online)
    assert len(LITE_FEATURES) == 17 and len(FULL_FEATURES) == 60
    assert not any("GENDER" in name or "EXT_SOURCE" in name for name in FULL_FEATURES)
    assert online.proposed_payment_income_ratio.iloc[0] == .5


@pytest.mark.parametrize("field,value", [("annual_income", 0), ("requested_amount", -1), ("age_years", 17),
    ("years_employed", 41), ("household_size", 1.5), ("dependent_children", 3), ("annual_income", float("inf")),
    ("education_level", "Higher education"), ("annual_income", True)])
def test_invalid_input_rejected(applicant, field, value):
    applicant[field] = value
    with pytest.raises(ContractError):
        lite_features(pd.DataFrame([applicant]))


def test_missing_required_vs_nullable(applicant):
    del applicant["years_employed"]
    with pytest.raises(ContractError):
        lite_features(pd.DataFrame([applicant]))
    applicant["years_employed"] = None
    row = lite_features(pd.DataFrame([applicant]))
    assert row.employment_tenure_missing.iloc[0] == 1
    assert row.occupation.iloc[0] == "MISSING"
    row["principal_income_ratio"] = 99
    with pytest.raises(ContractError):
        validate_features(row, "lite")


def test_quote_context(applicant):
    payload = dict(applicant, application_id="00000000-0000-0000-0000-000000000001", application_version=1,
                   as_of="2026-10-02T00:00:00Z", product_code="CASH_INSTALLMENT_V1", currency="XXX",
                   quote_id="00000000-0000-0000-0000-000000000002")
    quote = dict(payload, expires_at="2026-10-03T00:00:00Z")
    assert request_features(payload, currency="XXX", quote=quote).shape == (1, 17)
    quote["requested_amount"] = 1
    with pytest.raises(ContractError):
        request_features(payload, currency="XXX", quote=quote)


def test_full_contract_and_manifest_gate(data_root):
    full = build_feature_table(feature_set="full")
    assert set(FULL_FEATURES).issubset(full.columns)
    assert full.installment_due_count.eq(3).all()
    assert full.installment_late_count.eq(2).all()
    manifest = json.loads((data_root / "adapter_manifest.json").read_text())
    manifest["schedule_complete"] = False
    (data_root / "adapter_manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ContractError, match="schedule_complete"):
        build_feature_table(feature_set="full")  # Even a cache hit cannot bypass evidence gates.


def test_cache_invalidates_and_overlap_rejected(data_root):
    first = build_feature_table(feature_set="lite")
    path = data_root / "application_train.csv"
    source = pd.read_csv(path)
    source.loc[0, "AMT_INCOME_TOTAL"] *= 2
    source.to_csv(path, index=False)
    second = build_feature_table(feature_set="lite")
    assert second.annual_income.iloc[0] == first.annual_income.iloc[0] * 2
    test = pd.read_csv(data_root / "application_test.csv")
    test.loc[0, "SK_ID_CURR"] = source.SK_ID_CURR.iloc[0]
    test.to_csv(data_root / "application_test.csv", index=False)
    with pytest.raises(ContractError, match="overlap"):
        build_feature_table(feature_set="lite")


def test_history_adapter_parity_and_confirmed_empty(data_root):
    from creditiq_ml.features import history_features
    from creditiq_ml.contracts import HISTORY_GROUPS, HISTORY_FEATURES
    from creditiq_ml.io import load
    context = json.loads((data_root / "adapter_manifest.json").read_text())
    tables = {key: load(key) for key in HISTORY_GROUPS}
    schedule = pd.read_csv(data_root / "installment_schedule.csv")
    offline = build_feature_table(feature_set="full").set_index("SK_ID_CURR")
    customer = int(offline.index[0])
    online = history_features([customer], tables, schedule, context).set_index("SK_ID_CURR")
    pd.testing.assert_frame_equal(offline.loc[[customer], HISTORY_FEATURES], online[HISTORY_FEATURES])
    empty = {key: frame.iloc[:0] for key, frame in tables.items()}
    for entry in context["sources"].values():
        entry["state"] = "CONFIRMED_EMPTY"
    no_history = history_features([customer], empty, schedule.iloc[:0], context).iloc[0]
    assert no_history.bureau_account_count == 0 and no_history.installment_due_count == 0
    assert np.isnan(no_history.installment_mean_signed_delay)
    context["sources"]["bureau"]["state"] = "UNAVAILABLE"
    with pytest.raises(ContractError, match="incomplete"):
        history_features([customer], empty, schedule.iloc[:0], context)


def test_malformed_tenure_not_imputed_and_exclusions_recorded(data_root):
    source = pd.read_csv(data_root / "application_train.csv").iloc[:2].copy()
    source["DAYS_EMPLOYED"] = source.DAYS_EMPLOYED.astype(object)
    source.loc[0, "DAYS_EMPLOYED"] = "bad-number"
    result, excluded = application_features(source, return_exclusions=True)
    assert len(result) == 1 and len(excluded) == 1
