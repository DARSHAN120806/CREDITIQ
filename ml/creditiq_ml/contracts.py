"""Versioned semantic contracts shared by training and serving."""
from __future__ import annotations
from datetime import datetime
from uuid import UUID
from decimal import Decimal, InvalidOperation
import numpy as np
import pandas as pd

PRODUCT = "CASH_INSTALLMENT_V1"
TARGET_VERSION = "home-credit-target-unverified-horizon-v1"
BASE_NUMERIC = ["age_years", "years_employed", "annual_income", "requested_amount", "quoted_monthly_payment", "household_size", "dependent_children"]
CATEGORICAL = ["employment_type", "education_level", "occupation", "housing_status"]
DERIVED = ["employment_tenure_missing", "proposed_payment_income_ratio", "principal_income_ratio", "income_per_household_member", "employed_age_ratio", "payment_principal_ratio"]
LITE_FEATURES = BASE_NUMERIC + CATEGORICAL + DERIVED
HISTORY_GROUPS = {
    "bureau": ["bureau_account_count", "bureau_active_count", "bureau_closed_count", "bureau_overdue_count", "bureau_total_credit", "bureau_total_debt", "bureau_total_overdue", "bureau_max_dpd", "bureau_oldest_account_age_days", "bureau_newest_account_age_days"],
    "bureau_balance": ["bureau_observed_status_months", "bureau_delinquent_months", "bureau_severe_months", "bureau_late_month_ratio"],
    "previous_application": ["previous_application_count", "previous_approved_count", "previous_refused_count", "previous_refusal_rate", "previous_applications_365d", "days_since_previous_application"],
    "installments_payments": ["installment_due_count", "installment_fully_paid_count", "installment_late_count", "installment_unpaid_overdue_count", "installment_late_rate", "installment_mean_signed_delay", "installment_mean_overdue_days", "installment_max_overdue_days", "installment_mean_paid_ratio"],
    "pos_cash_balance": ["pos_loan_count", "pos_active_loan_count", "pos_observed_months", "pos_max_dpd", "pos_mean_dpd", "pos_late_month_ratio"],
    "credit_card_balance": ["card_account_count", "card_current_balance", "card_current_limit", "card_current_utilization", "card_historical_mean_utilization", "card_historical_max_utilization", "card_max_dpd", "card_late_month_ratio"],
}
HISTORY_FEATURES = [c for cols in HISTORY_GROUPS.values() for c in cols]
FULL_FEATURES = LITE_FEATURES + HISTORY_FEATURES
MAPS = {
    "employment_type": dict(zip(["Working", "Commercial associate", "State servant", "Pensioner", "Unemployed", "Student", "Businessman", "Maternity leave"], ["WORKING", "COMMERCIAL_ASSOCIATE", "STATE_SERVANT", "PENSIONER", "UNEMPLOYED", "STUDENT", "BUSINESSMAN", "MATERNITY_LEAVE"])),
    "education_level": {"Lower secondary": "LOWER_SECONDARY", "Secondary / secondary special": "SECONDARY", "Incomplete higher": "INCOMPLETE_HIGHER", "Higher education": "HIGHER", "Academic degree": "ACADEMIC_DEGREE"},
    "housing_status": dict(zip(["House / apartment", "With parents", "Rented apartment", "Municipal apartment", "Office apartment", "Co-op apartment"], ["OWN_OR_APARTMENT", "WITH_PARENTS", "RENTED", "MUNICIPAL", "OFFICE", "COOPERATIVE"])),
    "occupation": dict(zip(["Laborers", "Core staff", "Accountants", "Managers", "Drivers", "Sales staff", "Cleaning staff", "Cooking staff", "Private service staff", "Medicine staff", "Security staff", "High skill tech staff", "Waiters/barmen staff", "Low-skill Laborers", "Realty agents", "Secretaries", "IT staff", "HR staff"], ["LABORER", "CORE_STAFF", "ACCOUNTANT", "MANAGER", "DRIVER", "SALES", "CLEANING", "COOKING", "PRIVATE_SERVICE", "MEDICAL", "SECURITY", "HIGH_TECH", "WAITING_BAR", "LOW_SKILL_LABOR", "REALTY_AGENT", "SECRETARY", "IT", "HR"])),
}
VOCABULARIES = {c: sorted(set(m.values()) | {"OTHER"} | ({"MISSING"} if c in ("occupation", "housing_status") else set())) for c, m in MAPS.items()}
REQUIRED = BASE_NUMERIC + ["employment_type", "education_level"]


class ContractError(ValueError):
    """Invalid/unsupported data: no score may be fabricated."""


def feature_names(variant):
    if variant not in ("lite", "full"):
        raise ContractError("variant must be lite or full")
    return list(LITE_FEATURES if variant == "lite" else FULL_FEATURES)


def lite_features(frame):
    missing = set(REQUIRED) - set(frame.columns)
    if missing or frame.empty or frame.columns.duplicated().any():
        raise ContractError(f"Missing required fields or invalid frame: {sorted(missing)}")
    x = frame.reindex(columns=BASE_NUMERIC + CATEGORICAL).copy()
    for col in BASE_NUMERIC:
        if x[col].map(lambda v: isinstance(v, (bool, np.bool_))).any():
            raise ContractError(f"Boolean is not a number: {col}")
        try:
            x[col] = pd.to_numeric(x[col], errors="raise").astype(float)
        except (ValueError, TypeError) as exc:
            raise ContractError(f"Invalid numeric field: {col}") from exc
        if np.isinf(x[col]).any() or (col != "years_employed" and x[col].isna().any()):
            raise ContractError(f"Non-finite or missing: {col}")
    if (x.age_years < 18).any():
        raise ContractError("age_years must be >=18")
    if ((x.years_employed < 0) | (x.years_employed > x.age_years)).any():
        raise ContractError("Employment tenure must be between zero and age, or null")
    for col in ("annual_income", "requested_amount", "quoted_monthly_payment"):
        if (x[col] <= 0).any():
            raise ContractError(f"{col} must be positive")
    for col, minimum in (("household_size", 1), ("dependent_children", 0)):
        if ((x[col] < minimum) | (x[col] % 1 != 0)).any():
            raise ContractError(f"{col} must be an integer >= {minimum}")
    if (x.dependent_children > x.household_size - 1).any():
        raise ContractError("dependent_children exceeds household_size-1")
    for col in CATEGORICAL:
        if col in ("occupation", "housing_status"):
            x[col] = x[col].fillna("MISSING")
        if not x[col].isin(VOCABULARIES[col]).all():
            raise ContractError(f"Unsupported category in {col}; use canonical vocabulary")
        x[col] = x[col].astype(object)
    x["employment_tenure_missing"] = x.years_employed.isna().astype(int)
    x["proposed_payment_income_ratio"] = x.quoted_monthly_payment / (x.annual_income / 12)
    x["principal_income_ratio"] = x.requested_amount / x.annual_income
    x["income_per_household_member"] = x.annual_income / x.household_size
    x["employed_age_ratio"] = x.years_employed / x.age_years
    x["payment_principal_ratio"] = x.quoted_monthly_payment / x.requested_amount
    if np.isinf(x[DERIVED].to_numpy(dtype=float)).any():
        raise ContractError("Derived ratio overflow")
    return x[LITE_FEATURES]


def validate_features(frame, variant):
    names = feature_names(variant)
    if set(names) - set(frame.columns):
        raise ContractError("Incomplete feature vector; use the raw-input adapter first")
    canonical = lite_features(frame)
    for col in DERIVED:
        try:
            same = np.allclose(pd.to_numeric(frame[col]), canonical[col], equal_nan=True, rtol=1e-10, atol=1e-12)
        except (ValueError, TypeError):
            same = False
        if not same:
            raise ContractError(f"Derived feature mismatch: {col}")
    if variant == "full":
        for col in HISTORY_FEATURES:
            values = pd.to_numeric(frame[col], errors="raise").astype(float)
            if np.isinf(values).any():
                raise ContractError(f"Non-finite history: {col}")
            if col not in ("installment_mean_signed_delay", "card_current_balance") and (values < 0).any():
                raise ContractError(f"Negative history: {col}")
            if col.endswith(("_count", "_months", "_365d")) and (values.isna().any() or (values % 1 != 0).any()):
                raise ContractError(f"Invalid history count: {col}")
            if col.endswith(("_rate", "_ratio")) and (values > 1).any():
                raise ContractError(f"Invalid history fraction: {col}")
            canonical[col] = values
    return canonical[names]


def request_features(payload, *, currency, quote):
    """quote is trusted server context, not a client assertion of verification."""
    metadata = ["application_id", "application_version", "as_of", "product_code", "currency", "quote_id"]
    if any(k not in payload for k in metadata):
        raise ContractError("Missing request metadata")
    try:
        UUID(str(payload["application_id"])); UUID(str(payload["quote_id"]))
        timestamp = datetime.fromisoformat(str(payload["as_of"]).replace("Z", "+00:00"))
        expiry = datetime.fromisoformat(str(quote["expires_at"]).replace("Z", "+00:00"))
    except (ValueError, TypeError, KeyError) as exc:
        raise ContractError("Invalid request identity, timestamp or quote") from exc
    if timestamp.tzinfo is None or expiry.tzinfo is None or timestamp.utcoffset().total_seconds() != 0:
        raise ContractError("as_of must be timezone-aware UTC")
    if type(payload["application_version"]) is not int or payload["application_version"] < 1:
        raise ContractError("application_version must be a positive integer")
    if payload["product_code"] != PRODUCT or payload["currency"] != currency:
        raise ContractError("Unsupported product/currency")
    if expiry <= timestamp:
        raise ContractError("Expired quote at decision time")
    for key in ("application_id", "application_version", "quote_id", "currency", "requested_amount", "quoted_monthly_payment"):
        if key not in quote or str(payload.get(key)) != str(quote[key]):
            if key in ("requested_amount", "quoted_monthly_payment"):
                try:
                    if Decimal(str(payload.get(key))) == Decimal(str(quote.get(key))):
                        continue
                except InvalidOperation:
                    pass
            raise ContractError(f"Quote mismatch: {key}")
    return lite_features(pd.DataFrame([payload]))
