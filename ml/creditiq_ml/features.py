"""Canonical application and as-of history features; preserves the original module/CLI."""
from __future__ import annotations
import json
import logging
import numpy as np
import pandas as pd
from . import config as C
from .io import load, exists
from .contracts import (ContractError, MAPS, HISTORY_GROUPS, HISTORY_FEATURES,
                        lite_features, feature_names, validate_features)
from .provenance import source_manifest, input_manifest, fingerprint, write_json, sha256

log = logging.getLogger(__name__)


def _div(a, b):
    return a / b.replace(0, np.nan)


def _required(df, columns):
    missing = set(columns) - set(df.columns)
    if missing:
        raise ContractError(f"Missing source columns: {sorted(missing)}")


def _unique(df, keys):
    _required(df, keys)
    if df[keys].isna().any().any() or df.duplicated(keys).any():
        raise ContractError(f"Missing or duplicate source key: {keys}")


def _past(df, column, *, availability=False):
    _required(df, [column] + (["DAYS_AVAILABLE"] if availability else []))
    values = pd.to_numeric(df[column], errors="raise")
    if values.isna().any() or not np.isfinite(values).all():
        raise ContractError(f"Unknown event date: {column}")
    mask = values <= 0
    if availability:
        available = pd.to_numeric(df.DAYS_AVAILABLE, errors="raise")
        if available.isna().any() or not np.isfinite(available).all():
            raise ContractError("Unknown availability date")
        mask &= available <= 0
    return df.loc[mask].copy()


def _sum_known(s):
    # A total with any unknown constituent is unknown, not a partial known total.
    return s.sum() if s.notna().all() else np.nan


def _agg(df, spec):
    _required(df, [C.ID_COL] + [v[0] for v in spec.values()])
    return df.groupby(C.ID_COL).agg(**spec).reset_index()


def application_features(df, *, return_exclusions=False):
    _unique(df, [C.ID_COL])
    mapping = {"age_years": "DAYS_BIRTH", "years_employed": "DAYS_EMPLOYED",
               "annual_income": "AMT_INCOME_TOTAL", "requested_amount": "AMT_CREDIT",
               "quoted_monthly_payment": "AMT_ANNUITY", "household_size": "CNT_FAM_MEMBERS",
               "dependent_children": "CNT_CHILDREN", "employment_type": "NAME_INCOME_TYPE",
               "education_level": "NAME_EDUCATION_TYPE", "occupation": "OCCUPATION_TYPE",
               "housing_status": "NAME_HOUSING_TYPE"}
    _required(df, ["NAME_CONTRACT_TYPE"] + [v for k, v in mapping.items() if k not in ("occupation", "housing_status")])
    raw = pd.DataFrame({k: df[v] if v in df else pd.Series(np.nan, index=df.index) for k, v in mapping.items()})
    raw["age_years"] = -pd.to_numeric(raw.age_years, errors="coerce") / 365.25
    raw["years_employed"] = -pd.to_numeric(raw.years_employed, errors="coerce").replace(365243, np.nan) / 365.25
    malformed_tenure = df.DAYS_EMPLOYED.notna() & pd.to_numeric(df.DAYS_EMPLOYED, errors="coerce").isna()
    raw.loc[malformed_tenure, "years_employed"] = -1  # Reject malformed text, don't turn it into an allowed null.
    for col, vocabulary in MAPS.items():
        source = raw[col]
        raw[col] = source.map(vocabulary).fillna("OTHER")
        raw.loc[source.isna(), col] = "MISSING" if col in ("occupation", "housing_status") else None
    eligible = df.NAME_CONTRACT_TYPE.eq("Cash loans")
    exclusions = [{"id": int(df.loc[i, C.ID_COL]), "reason": "unsupported_product"} for i in df.index[~eligible]]
    # Validate in batches first; only use row-level checks when needed to record precise exclusions.
    def validate_batch(batch):
        if batch.empty:
            return []
        try:
            return [lite_features(batch)]
        except ContractError as exc:
            if len(batch) == 1:
                exclusions.append({"id": int(df.loc[batch.index[0], C.ID_COL]), "reason": str(exc)})
                return []
            middle = len(batch) // 2
            return validate_batch(batch.iloc[:middle]) + validate_batch(batch.iloc[middle:])
    batches = validate_batch(raw.loc[eligible])
    features = pd.concat(batches) if batches else pd.DataFrame(columns=feature_names("lite"))
    valid = list(features.index)
    result = df.loc[valid, [c for c in (C.ID_COL, C.TARGET, "IS_TRAIN") if c in df]].join(features)
    return (result, exclusions) if return_exclusions else result


def bureau_features(b=None, bb=None):
    b = load("bureau") if b is None else b.copy()
    bb = load("bureau_balance") if bb is None else bb.copy()
    _unique(b, ["SK_ID_BUREAU"])
    b = _past(b, "DAYS_CREDIT", availability=True)
    _required(b, ["CREDIT_ACTIVE", "CREDIT_DAY_OVERDUE", "AMT_CREDIT_SUM", "AMT_CREDIT_SUM_DEBT", "AMT_CREDIT_SUM_OVERDUE"])
    if not b.CREDIT_ACTIVE.isin(["Active", "Closed", "Sold", "Bad debt"]).all():
        raise ContractError("Unknown bureau account status")
    if (b.CREDIT_DAY_OVERDUE < 0).any():
        raise ContractError("Negative bureau DPD")
    b["active"] = b.CREDIT_ACTIVE.eq("Active").astype(int)
    b["closed"] = b.CREDIT_ACTIVE.eq("Closed").astype(int)
    b["overdue"] = b.CREDIT_DAY_OVERDUE.gt(0).where(b.CREDIT_DAY_OVERDUE.notna())
    b["age"] = -b.DAYS_CREDIT
    out = _agg(b, {
        "bureau_account_count": ("SK_ID_BUREAU", "nunique"), "bureau_active_count": ("active", "sum"),
        "bureau_closed_count": ("closed", "sum"), "bureau_overdue_count": ("overdue", _sum_known),
        "bureau_total_credit": ("AMT_CREDIT_SUM", _sum_known), "bureau_total_debt": ("AMT_CREDIT_SUM_DEBT", _sum_known),
        "bureau_total_overdue": ("AMT_CREDIT_SUM_OVERDUE", _sum_known), "bureau_max_dpd": ("CREDIT_DAY_OVERDUE", "max"),
        "bureau_oldest_account_age_days": ("age", "max"), "bureau_newest_account_age_days": ("age", "min")})
    _unique(bb, ["SK_ID_BUREAU", "MONTHS_BALANCE"])
    bb = _past(bb, "MONTHS_BALANCE", availability=True)
    if not bb.SK_ID_BUREAU.isin(b.SK_ID_BUREAU).all():
        raise ContractError("Orphan/unavailable bureau balance account")
    bb = bb.merge(b[["SK_ID_BUREAU", C.ID_COL]], on="SK_ID_BUREAU", validate="many_to_one")
    status = bb.STATUS.astype(str)
    if not status.isin(["0", "1", "2", "3", "4", "5", "C", "X"]).all():
        raise ContractError("Unknown bureau monthly status")
    bb["known"] = status.isin(list("012345")).astype(int)
    bb["late"] = status.isin(list("12345")).astype(int)
    bb["severe"] = status.isin(list("345")).astype(int)
    bal = _agg(bb, {"bureau_observed_status_months": ("known", "sum"),
                   "bureau_delinquent_months": ("late", "sum"), "bureau_severe_months": ("severe", "sum")})
    out = out.merge(bal, on=C.ID_COL, how="left", validate="one_to_one")
    counts = HISTORY_GROUPS["bureau_balance"][:3]
    out[counts] = out[counts].fillna(0)
    out["bureau_late_month_ratio"] = _div(out.bureau_delinquent_months, out.bureau_observed_status_months)
    return out


def previous_features(p=None):
    p = load("previous_application") if p is None else p.copy()
    _unique(p, ["SK_ID_PREV"])
    p = _past(p, "DAYS_DECISION", availability=True)
    _required(p, ["NAME_CONTRACT_STATUS"])
    if not p.NAME_CONTRACT_STATUS.isin(["Approved", "Refused", "Canceled", "Unused offer"]).all():
        raise ContractError("Unknown previous application status")
    p["approved"] = p.NAME_CONTRACT_STATUS.eq("Approved").astype(int)
    p["refused"] = p.NAME_CONTRACT_STATUS.eq("Refused").astype(int)
    p["recent"] = p.DAYS_DECISION.ge(-365).astype(int)
    p["age"] = -p.DAYS_DECISION
    out = _agg(p, {"previous_application_count": ("SK_ID_PREV", "nunique"),
                   "previous_approved_count": ("approved", "sum"), "previous_refused_count": ("refused", "sum"),
                   "previous_refusal_rate": ("refused", "mean"), "previous_applications_365d": ("recent", "sum"),
                   "days_since_previous_application": ("age", "min")})
    return out


INSTALLMENT_KEYS = [C.ID_COL, "SK_ID_PREV", "NUM_INSTALMENT_NUMBER", "NUM_INSTALMENT_VERSION"]


def installments_features(payments=None, schedule=None, tolerance=.01):
    """Reconcile one effective schedule; relative dates are days from T=0."""
    if not np.isfinite(tolerance) or not 0 <= tolerance <= .01:
        raise ContractError("Invalid minor-unit tolerance")
    p = load("installments_payments") if payments is None else payments.copy()
    s = pd.read_csv(C.RAW_DIR / "installment_schedule.csv") if schedule is None else schedule.copy()
    _unique(s, INSTALLMENT_KEYS)
    _required(s, ["DAYS_INSTALMENT", "AMT_INSTALMENT", "DAYS_AVAILABLE"])
    s = _past(s, "DAYS_AVAILABLE")
    if s.groupby("SK_ID_PREV")[C.ID_COL].nunique().gt(1).any():
        raise ContractError("Conflicting installment loan owner")
    if s.duplicated([C.ID_COL, "SK_ID_PREV", "NUM_INSTALMENT_NUMBER"]).any():
        raise ContractError("Ambiguous effective schedule versions")
    if s[["DAYS_INSTALMENT", "AMT_INSTALMENT"]].isna().any().any() or not np.isfinite(s[["DAYS_INSTALMENT", "AMT_INSTALMENT"]]).all().all() or (s.AMT_INSTALMENT <= 0).any():
        raise ContractError("Invalid contractual schedule")
    _required(p, INSTALLMENT_KEYS + ["PAYMENT_ID", "DAYS_ENTRY_PAYMENT", "AMT_PAYMENT", "DAYS_AVAILABLE"])
    # Repeated event ID is safe to deduplicate only when every value agrees.
    duplicate_ids = p[p.PAYMENT_ID.duplicated(False)]
    if len(duplicate_ids) and duplicate_ids.groupby("PAYMENT_ID").nunique(dropna=False).gt(1).any().any():
        raise ContractError("Conflicting duplicate payment identity")
    if p.PAYMENT_ID.isna().any():
        raise ContractError("Missing payment event identity")
    p = p.drop_duplicates("PAYMENT_ID")
    p = _past(p, "DAYS_ENTRY_PAYMENT", availability=True)
    if p.AMT_PAYMENT.isna().any() or not np.isfinite(p.AMT_PAYMENT).all() or (p.AMT_PAYMENT < 0).any():
        raise ContractError("Unknown/negative payments need reversal reconciliation")
    expected = s[INSTALLMENT_KEYS + ["DAYS_INSTALMENT", "AMT_INSTALMENT"]]
    # If the payment rows also repeat schedule fields, verify them rather than trusting them.
    joined = p.merge(expected, on=INSTALLMENT_KEYS, how="left", suffixes=("_payment", ""), validate="many_to_one", indicator=True)
    if joined._merge.ne("both").any():
        raise ContractError("Payment references unknown effective schedule")
    for col in ("DAYS_INSTALMENT", "AMT_INSTALMENT"):
        if col + "_payment" in joined and not np.allclose(joined[col + "_payment"], joined[col], atol=1e-8, rtol=0):
            raise ContractError("Conflicting installment schedule amounts/dates")
    joined = joined.sort_values(INSTALLMENT_KEYS + ["DAYS_ENTRY_PAYMENT", "PAYMENT_ID"])
    joined["cumulative"] = joined.groupby(INSTALLMENT_KEYS).AMT_PAYMENT.cumsum()
    completed = joined[joined.cumulative >= joined.AMT_INSTALMENT - tolerance]
    completion = completed.groupby(INSTALLMENT_KEYS).DAYS_ENTRY_PAYMENT.min().rename("completion")
    paid = joined.groupby(INSTALLMENT_KEYS).AMT_PAYMENT.sum().rename("paid")
    s = s.join(completion, on=INSTALLMENT_KEYS).join(paid, on=INSTALLMENT_KEYS)
    s = s[s.DAYS_INSTALMENT <= 0].copy()
    s["paid"] = s.paid.fillna(0)
    s["complete"] = s.completion.notna().astype(int)
    s["delay"] = s.completion - s.DAYS_INSTALMENT
    s["unpaid_overdue"] = (s.completion.isna() & s.DAYS_INSTALMENT.lt(0)).astype(int)
    s["late"] = (s.delay.gt(0) | s.unpaid_overdue.eq(1)).astype(int)
    s["overdue"] = (s.completion.fillna(0) - s.DAYS_INSTALMENT).clip(lower=0)
    s["ratio"] = (s.paid / s.AMT_INSTALMENT).clip(upper=1)
    return _agg(s, {"installment_due_count": ("SK_ID_PREV", "size"), "installment_fully_paid_count": ("complete", "sum"),
                    "installment_late_count": ("late", "sum"), "installment_unpaid_overdue_count": ("unpaid_overdue", "sum"),
                    "installment_late_rate": ("late", "mean"), "installment_mean_signed_delay": ("delay", "mean"),
                    "installment_mean_overdue_days": ("overdue", "mean"), "installment_max_overdue_days": ("overdue", "max"),
                    "installment_mean_paid_ratio": ("ratio", "mean")})


def _snapshots(df):
    _unique(df, ["SK_ID_PREV", "MONTHS_BALANCE"])
    if df.groupby("SK_ID_PREV")[C.ID_COL].nunique().gt(1).any():
        raise ContractError("Conflicting account owner")
    df = _past(df, "MONTHS_BALANCE", availability=True)
    if (df.SK_DPD < 0).any():
        raise ContractError("Negative DPD")
    return df


def _latest_per_loan(df):
    return df.sort_values("MONTHS_BALANCE").drop_duplicates("SK_ID_PREV", keep="last")


def pos_features(pos=None):
    pos = _snapshots(load("pos_cash_balance") if pos is None else pos.copy())
    pos["late"] = pos.SK_DPD.gt(0).where(pos.SK_DPD.notna()).astype(float)
    out = _agg(pos, {"pos_loan_count": ("SK_ID_PREV", "nunique"), "pos_observed_months": ("MONTHS_BALANCE", "size"),
                     "pos_max_dpd": ("SK_DPD", "max"), "pos_mean_dpd": ("SK_DPD", "mean"), "pos_late_month_ratio": ("late", "mean")})
    last = _latest_per_loan(pos)
    if last.NAME_CONTRACT_STATUS.isna().any():
        raise ContractError("Unknown POS latest status")
    last = last.assign(active=last.NAME_CONTRACT_STATUS.eq("Active").astype(int))
    return out.merge(_agg(last, {"pos_active_loan_count": ("active", "sum")}), on=C.ID_COL, validate="one_to_one")


def credit_card_features(cc=None):
    cc = _snapshots(load("credit_card_balance") if cc is None else cc.copy())
    _required(cc, ["AMT_BALANCE", "AMT_CREDIT_LIMIT_ACTUAL", "NAME_CONTRACT_STATUS"])
    if (cc.AMT_CREDIT_LIMIT_ACTUAL < 0).any():
        raise ContractError("Negative credit limit")
    cc["util"] = cc.AMT_BALANCE.clip(lower=0) / cc.AMT_CREDIT_LIMIT_ACTUAL.where(cc.AMT_CREDIT_LIMIT_ACTUAL > 0)
    cc["late"] = cc.SK_DPD.gt(0).where(cc.SK_DPD.notna()).astype(float)
    out = _agg(cc, {"card_account_count": ("SK_ID_PREV", "nunique"),
                    "card_historical_mean_utilization": ("util", "mean"), "card_historical_max_utilization": ("util", "max"),
                    "card_max_dpd": ("SK_DPD", "max"), "card_late_month_ratio": ("late", "mean")})
    last = _latest_per_loan(cc)
    if last.NAME_CONTRACT_STATUS.isna().any():
        raise ContractError("Unknown card latest status")
    active = last[last.NAME_CONTRACT_STATUS.eq("Active")].copy()
    active["nonnegative_balance"] = active.AMT_BALANCE.clip(lower=0)
    active["invalid_limit"] = (active.AMT_BALANCE.gt(0) & (active.AMT_CREDIT_LIMIT_ACTUAL.isna() | active.AMT_CREDIT_LIMIT_ACTUAL.le(0))).astype(int)
    current = _agg(active, {"card_current_balance": ("AMT_BALANCE", _sum_known),
                            "card_current_limit": ("AMT_CREDIT_LIMIT_ACTUAL", _sum_known),
                            "positive_balance": ("nonnegative_balance", _sum_known), "invalid_limit": ("invalid_limit", "max")})
    current["card_current_utilization"] = _div(current.positive_balance, current.card_current_limit).where(current.invalid_limit.eq(0))
    out = out.merge(current, on=C.ID_COL, how="left", indicator=True, validate="one_to_one")
    no_active = out._merge.eq("left_only")
    out.loc[no_active, ["card_current_balance", "card_current_limit"]] = 0
    return out[[C.ID_COL] + HISTORY_GROUPS["credit_card_balance"]]


def history_features(customer_ids, tables, schedule, context):
    """Shared offline/online history adapter; no client-provided aggregate shortcuts."""
    for gate in ("schedule_complete", "schedule_versions_resolved", "payment_identity_verified", "availability_verified"):
        if context.get(gate) is not True:
            raise ContractError(f"Full unavailable: {gate}")
    for key in HISTORY_GROUPS:
        entry = context.get("sources", {}).get(key, {})
        if key not in tables or entry.get("state") not in ("COMPLETE", "CONFIRMED_EMPTY") or not entry.get("evidence"):
            raise ContractError(f"Full source incomplete: {key}")
        if entry["state"] == "CONFIRMED_EMPTY" and len(tables[key]):
            raise ContractError(f"Nonempty source declared empty: {key}")
    app = pd.DataFrame({C.ID_COL: list(customer_ids)})
    _unique(app, [C.ID_COL])
    previous = tables["previous_application"]
    _unique(previous, ["SK_ID_PREV"])
    for source in (schedule, tables["installments_payments"], tables["pos_cash_balance"], tables["credit_card_balance"]):
        owners = source[["SK_ID_PREV", C.ID_COL]].drop_duplicates().merge(
            previous[["SK_ID_PREV", C.ID_COL]], on="SK_ID_PREV", how="left", suffixes=("", "_previous"), validate="many_to_one")
        if not owners[C.ID_COL].eq(owners[C.ID_COL + "_previous"]).all():
            raise ContractError("History account does not match previous-application owner")
    results = [(("bureau", "bureau_balance"), bureau_features(tables["bureau"], tables["bureau_balance"])),
               (("previous_application",), previous_features(previous)),
               (("installments_payments",), installments_features(tables["installments_payments"], schedule)),
               (("pos_cash_balance",), pos_features(tables["pos_cash_balance"])),
               (("credit_card_balance",), credit_card_features(tables["credit_card_balance"]))]
    for keys, table in results:
        columns = [c for key in keys for c in HISTORY_GROUPS[key]]
        app = app.merge(table, on=C.ID_COL, how="left", validate="one_to_one", indicator=True)
        absent = app._merge.eq("left_only")
        zero_columns = [c for c in columns if c.endswith(("_count", "_months", "_365d")) or c in
                        ("bureau_total_credit", "bureau_total_debt", "bureau_total_overdue", "card_current_balance", "card_current_limit")]
        app.loc[absent, zero_columns] = 0
        app = app.drop(columns="_merge")
    app[HISTORY_FEATURES] = app[HISTORY_FEATURES].astype(float)
    return app[[C.ID_COL] + HISTORY_FEATURES]


def build_feature_table(use_cache=True, feature_set="lite"):
    manifest = source_manifest(feature_set)
    provenance = input_manifest(feature_set)
    digest = fingerprint(provenance)
    C.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    cache = C.PROCESSED_DIR / f"features_{feature_set}_{digest[:16]}.parquet"
    if use_cache and cache.exists():
        report_path = cache.with_suffix(".json")
        if report_path.exists() and json.loads(report_path.read_text()).get("parquet_sha256") == sha256(cache):
            cached = pd.read_parquet(cache)
            validate_features(cached, feature_set)
            return cached
        log.warning("Cache integrity failed; rebuilding %s", cache.name)
    train = load("application_train").assign(IS_TRAIN=1)
    _unique(train, [C.ID_COL])
    if train[C.TARGET].isna().any() or not train[C.TARGET].isin([0, 1]).all():
        raise ContractError("TARGET must be binary and nonmissing")
    parts = [train]
    if exists("application_test"):
        test = load("application_test").assign(IS_TRAIN=0)
        _unique(test, [C.ID_COL])
        if set(train[C.ID_COL]) & set(test[C.ID_COL]):
            raise ContractError("Train/test customer overlap")
        if C.TARGET in test and test[C.TARGET].notna().any():
            raise ContractError("Competition test contains labels")
        parts.append(test)
    app, exclusions = application_features(pd.concat(parts, ignore_index=True), return_exclusions=True)
    if app.empty:
        raise ContractError("No valid application rows")
    if feature_set == "full":
        histories = history_features(app[C.ID_COL], {key: load(key) for key in HISTORY_GROUPS},
                                    pd.read_csv(C.RAW_DIR / "installment_schedule.csv"), manifest)
        app = app.merge(histories, on=C.ID_COL, how="left", validate="one_to_one")
    validated = validate_features(app, feature_set)
    app[feature_names(feature_set)] = validated
    report = {"fingerprint": digest, "inputs": provenance, "adapter": manifest, "excluded_rows": exclusions,
              "eligible_rows": len(app), "quality_missing_counts": app[feature_names(feature_set)].isna().sum().astype(int).to_dict()}
    app.to_parquet(cache, index=False)
    report["parquet_sha256"] = sha256(cache)
    write_json(cache.with_suffix(".json"), report)
    return app

