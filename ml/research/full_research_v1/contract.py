"""Independent FULL_RESEARCH_V1 snapshot feature definitions; never a serving contract."""
from creditiq_ml.contracts import LITE_FEATURES, CATEGORICAL

VERSION = "FULL_RESEARCH_V1"
SOURCES = ["bureau", "bureau_balance", "previous_application", "pos", "card", "installment"]
FEATURES = []


def add(name, source, definition, concern, recommendation="KEEP"):
    FEATURES.append(dict(feature=name, source_dataset=source, definition=definition,
                         data_quality_concerns=concern, recommendation=recommendation,
                         dtype="category" if name in CATEGORICAL else "float64"))


BASE_DEFINITIONS = {
    "age_years": "-DAYS_BIRTH / 365.25", "years_employed": "-DAYS_EMPLOYED / 365.25; sentinel 365243 becomes null",
    "annual_income": "AMT_INCOME_TOTAL; annual-income research assumption", "requested_amount": "AMT_CREDIT",
    "quoted_monthly_payment": "AMT_ANNUITY; monthly-annuity research assumption",
    "household_size": "CNT_FAM_MEMBERS", "dependent_children": "CNT_CHILDREN",
    "employment_type": "Canonical NAME_INCOME_TYPE category", "education_level": "Canonical NAME_EDUCATION_TYPE category",
    "occupation": "Canonical OCCUPATION_TYPE; absent becomes MISSING", "housing_status": "Canonical NAME_HOUSING_TYPE; absent becomes MISSING",
    "employment_tenure_missing": "1 when years_employed is null", "proposed_payment_income_ratio": "quoted_monthly_payment / (annual_income / 12)",
    "principal_income_ratio": "requested_amount / annual_income", "income_per_household_member": "annual_income / household_size",
    "employed_age_ratio": "years_employed / age_years", "payment_principal_ratio": "quoted_monthly_payment / requested_amount",
}
for name in LITE_FEATURES:
    add(name, "application_train.csv", BASE_DEFINITIONS[name], "Existing Lite application transform reused read-only. Units remain research assumptions; MISSING is a category, not known information.")
for n in (1, 2, 3):
    add(f"external_source_{n}", "application_train.csv", f"Observed EXT_SOURCE_{n}, accepted only within [0,1]", "Opaque external score semantics/provider; benchmark-only. Missingness and distribution shift; require with/without-external-score ablation.")
for source in SOURCES:
    add(f"{source}_observed", source, "1 if at least one retained row is available for this borrower, else 0", "0 means no usable rows in the supplied extract, never verified absence of obligations.")

BUREAU = {
    "bureau_observed_accounts": "Count of unique retained SK_ID_BUREAU",
    "bureau_active_accounts": "Count with CREDIT_ACTIVE=Active among retained accounts",
    "bureau_closed_accounts": "Count with CREDIT_ACTIVE=Closed among retained accounts",
    "bureau_dpd_known_fraction": "Fraction with finite nonnegative CREDIT_DAY_OVERDUE",
    "bureau_overdue_account_fraction": "Fraction of known DPD accounts with CREDIT_DAY_OVERDUE>0",
    "bureau_overdue_account_count": "Number of known DPD accounts with CREDIT_DAY_OVERDUE>0; null if no DPD values known",
    "bureau_max_dpd": "Maximum known nonnegative CREDIT_DAY_OVERDUE",
    "bureau_oldest_account_days": "Maximum -DAYS_CREDIT",
    "bureau_newest_account_days": "Minimum -DAYS_CREDIT",
    "bureau_openings_365d": "Retained accounts with DAYS_CREDIT>=-365",
    "bureau_latest_update_age_days": "Minimum -DAYS_CREDIT_UPDATE",
    "bureau_currency1_accounts": "Count with CREDIT_CURRENCY=currency 1",
    "bureau_currency1_credit_sum": "Sum of nonnegative AMT_CREDIT_SUM for currency 1; null if any constituent unknown/invalid or no such accounts",
    "bureau_currency1_positive_debt_sum": "Sum max(AMT_CREDIT_SUM_DEBT,0) for currency 1; null if any debt unknown or no such accounts",
    "bureau_currency1_overdue_sum": "Sum nonnegative AMT_CREDIT_SUM_OVERDUE for currency 1; null if any constituent unknown/invalid",
    "bureau_currency1_debt_credit_ratio": "Positive debt sum / credit sum for currency 1 when denominator>0",
    "bureau_currency1_debt_known_fraction": "Fraction of currency 1 accounts with finite debt",
    "bureau_currency1_negative_debt_fraction": "Fraction of known currency 1 debts below zero (account-credit indicator)",
}
for name, definition in BUREAU.items():
    add(name, "bureau.csv", definition, "Only unique explicit bureau owners, DAYS_CREDIT<0 and DAYS_CREDIT_UPDATE<=0. Observed extract, not complete verified credit history. Currency-1 totals are never converted or treated as INR.")

BALANCE = {
    "bureau_balance_observed_months": "Count of retained mapped account-month rows",
    "bureau_balance_known_months": "Count of numeric STATUS values 0..5",
    "bureau_balance_late_fraction": "STATUS in 1..5 / numeric-status months",
    "bureau_balance_severe_fraction": "STATUS in 3..5 / numeric-status months",
    "bureau_balance_max_status": "Maximum numeric STATUS code; code is an ordinal, not days",
    "bureau_balance_unknown_fraction": "STATUS=X / retained rows",
    "bureau_balance_closed_fraction": "STATUS=C / retained rows",
    "bureau_balance_recent12_late_fraction": "STATUS in 1..5 / numeric-status months for MONTHS_BALANCE>=-12",
    "bureau_balance_latest_late_fraction": "Late fraction among numeric statuses in latest retained month of each mapped account",
}
for name, definition in BALANCE.items():
    add(name, "bureau_balance.csv + bureau.csv", definition, "Inner mapping to unique retained bureau IDs only; unmapped rows quarantined. MONTHS_BALANCE<0. Duplicate account-month groups excluded. Observed account-month weighted, not a complete borrower timeline.")

PREVIOUS = {
    "previous_observed_applications": "Count of unique retained SK_ID_PREV",
    "previous_approved_fraction": "Approved / retained applications with recognized status",
    "previous_refused_fraction": "Refused / retained applications with recognized status",
    "previous_canceled_fraction": "Canceled / retained applications with recognized status",
    "previous_applications_365d": "Count with DAYS_DECISION>=-365",
    "previous_applications_90d": "Count with DAYS_DECISION>=-90",
    "previous_recency_days": "Minimum -DAYS_DECISION",
    "previous_requested_amount_mean": "Mean finite nonnegative AMT_APPLICATION",
    "previous_approved_credit_mean": "Mean finite nonnegative AMT_CREDIT on Approved rows",
    "previous_approved_credit_request_ratio": "Mean AMT_CREDIT/AMT_APPLICATION on Approved rows, positive request and nonnegative credit",
}
for name, definition in PREVIOUS.items():
    add(name, "previous_application.csv", definition, "DAYS_DECISION<0; duplicate SK_ID_PREV excluded. Applications/approvals are not disbursed loans. Historical lender policy and selection bias.")

POS = {
    "pos_observed_months": "Retained account-month count", "pos_observed_accounts": "Distinct retained SK_ID_PREV",
    "pos_dpd_known_fraction": "Fraction with finite nonnegative SK_DPD", "pos_late_fraction": "SK_DPD>0 / known DPD months",
    "pos_max_dpd": "Maximum nonnegative SK_DPD", "pos_mean_dpd": "Mean nonnegative SK_DPD",
    "pos_max_tolerant_dpd": "Maximum nonnegative SK_DPD_DEF",
    "pos_recent12_late_fraction": "Known-DPD late fraction for MONTHS_BALANCE>=-12",
    "pos_latest_active_fraction": "Active / known-status latest retained snapshots per account",
    "pos_latest_snapshot_age_months": "Minimum -MONTHS_BALANCE across latest retained account snapshots",
}
for name, definition in POS.items():
    add(name, "POS_CASH_balance.csv", definition, "Explicit SK_ID_CURR; conflicting loan owners and duplicate account-month groups excluded. MONTHS_BALANCE<0; account-month weighting, source coverage and staleness matter.")

CARD = {
    "card_observed_months": "Retained account-month count", "card_observed_accounts": "Distinct retained SK_ID_PREV",
    "card_historical_utilization_mean": "Mean max(AMT_BALANCE,0)/AMT_CREDIT_LIMIT_ACTUAL for finite balance and positive finite limit",
    "card_historical_utilization_max": "Maximum valid observed utilization; values above 1 retained",
    "card_high_utilization_fraction": "Fraction of valid utilization observations >=0.9",
    "card_utilization_known_fraction": "Valid utilization observations / retained rows",
    "card_latest_positive_balance": "Sum max(balance,0) across latest retained Active snapshots; null if any active balance unknown or no observed active accounts",
    "card_latest_positive_limit": "Sum limits across latest retained Active snapshots; null if any limit nonpositive/unknown or no observed active accounts",
    "card_latest_utilization": "Latest active positive balance sum / latest active positive limit sum",
    "card_latest_snapshot_age_months": "Minimum -MONTHS_BALANCE among latest retained Active snapshots",
    "card_oldest_active_snapshot_age_months": "Maximum -MONTHS_BALANCE among latest retained Active snapshots",
    "card_late_fraction": "SK_DPD>0 / known nonnegative DPD months", "card_max_dpd": "Maximum nonnegative SK_DPD",
    "card_recent12_late_fraction": "Known-DPD late fraction for MONTHS_BALANCE>=-12",
    "card_negative_balance_fraction": "Negative AMT_BALANCE / finite observed balances",
    "card_atm_drawing_share_mean": "Mean AMT_DRAWINGS_ATM_CURRENT / AMT_DRAWINGS_CURRENT for positive total and ATM in [0,total]",
}
for name, definition in CARD.items():
    add(name, "credit_card_balance.csv", definition, "Explicit owners and unique past account-months only. Latest observed is not a live balance. Negative balances represent possible credits; utilization uses positive exposure. Limits/coverage/staleness explicitly reported.")

INSTALLMENT = {
    "installment_observed_single_records": "Count of retained single-row (borrower,loan,installment-number) groups",
    "installment_observed_accounts": "Distinct SK_ID_PREV in retained records",
    "installment_observed_record_late_fraction": "Fraction with DAYS_ENTRY_PAYMENT>DAYS_INSTALMENT",
    "installment_observed_late_records": "Count of retained records with positive payment-date delay",
    "installment_observed_mean_signed_delay": "Mean DAYS_ENTRY_PAYMENT-DAYS_INSTALMENT",
    "installment_observed_mean_late_delay": "Mean positive delay among late records only; null if none",
    "installment_observed_max_delay": "Maximum max(payment-date minus due-date,0)",
    "installment_observed_timing_std": "Population standard deviation of signed delays; null with fewer than 2 records",
    "installment_observed_paid_fraction_mean": "Mean min(AMT_PAYMENT/AMT_INSTALMENT,1) for retained records",
    "installment_observed_amount_covered_fraction": "Fraction with AMT_PAYMENT>=AMT_INSTALMENT; exact observed amount comparison, not verified contractual completion",
    "installment_observed_weighted_paid_fraction": "Sum min(AMT_PAYMENT,AMT_INSTALMENT) / sum AMT_INSTALMENT",
    "installment_observed_recent365_late_fraction": "Late fraction among retained records with DAYS_INSTALMENT>=-365",
    "installment_observed_payment_recency_days": "Minimum -DAYS_ENTRY_PAYMENT",
}
for name, definition in INSTALLMENT.items():
    add(name, "installments_payments.csv", definition, "Only due<0 and payment-date<0, finite amount>=0, scheduled amount>0, version>0. All repeated loan/number groups among past records excluded, including split payments or versions. Selection-biased observed records, not an effective schedule or verified payment identities. No unseen/missed obligation inference.")

for name, source, why in [
    ("true_installment_late_rate", "installments_payments.csv", "Requires complete effective schedule and reconciled identities; observed-record proxy is separately named"),
    ("unpaid_overdue_installment_count", "installments_payments.csv", "Never-paid obligations are absent/unverifiable"),
    ("contractual_installment_due_count", "installments_payments.csv", "No complete effective contractual schedule"),
    ("fully_repaid_installment_count", "installments_payments.csv", "No cumulative reconciliation of split/versioned records without verified identity"),
    ("current_installment_arrears_days", "installments_payments.csv", "Requires outstanding obligations and effective schedule"),
    ("true_installment_completion_ratio", "installments_payments.csv", "Unknown denominator and ambiguous partial/split payments"),
    ("missed_payment_count", "installments_payments.csv", "No payment row does not establish a missed obligation"),
    ("historical_availability_days", "all history sources", "Ingestion/knowledge-availability evidence absent; do not synthesize DAYS_AVAILABLE"),
    ("synthetic_payment_identity", "installments_payments.csv", "Row hashes or indices cannot establish distinct payment-event identities"),
    ("unmapped_bureau_status_features", "bureau_balance.csv", "Unresolved bureau-to-borrower mapping; quarantined rather than inferred"),
    ("bureau_debt_to_income_ratio", "bureau.csv + application_train.csv", "Cannot establish currency-1 units align with application income; retain within-currency debt/credit ratio instead"),
    ("all_currency_bureau_debt_sum", "bureau.csv", "No FX conversion; do not mix currency labels"),
    ("existing_monthly_emi_burden", "all history sources", "No verified complete current repayment-obligation schedule or common periodicity"),
    ("previous_actual_termination_features", "previous_application.csv", "Post-decision lifecycle fields risk label leakage and availability ambiguity; use DAYS_DECISION and application-time fields only"),
    ("card_payment_balance_completion_ratio", "credit_card_balance.csv", "Closing balance is not amount contractually due; payment/balance is not repayment completion"),
]:
    add(name, source, "Not generated", why, "DROP")

KEEP = [f["feature"] for f in FEATURES if f["recommendation"] == "KEEP"]
HISTORY = [f for f in KEEP if f not in LITE_FEATURES and not f.startswith("external_source_")]
