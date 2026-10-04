# Borrowing Planner design

**Status:** V1 implemented; see [BORROWING_PLANNER_API.md](BORROWING_PLANNER_API.md) and [BORROWING_PLANNER_VALIDATION.md](BORROWING_PLANNER_VALIDATION.md). No model, database migration, authentication behavior, installment behavior, or existing prediction API was changed.  
**Purpose:** give users a transparent view of monthly cash flow under a proposed loan. This is budgeting guidance, not credit approval or financial advice.

## Product boundary

The planner uses current amounts explicitly entered or confirmed by the user. It does not infer expenses or current debts from Home Credit training data, from a risk probability, from historical installment discipline, or from the existing illustrative quote. The Lite and FULL_RESEARCH_V1_NO_EXT risk models remain independent of planner calculations. Admin access and application APIs remain unchanged.

V1 should be stateless: one authenticated calculation request, one response, no new table or migration. Do not force a plan into `loan_quotes` (that table represents the application quote) or `reports` (export job). If users later need saved plans, add a dedicated owner-scoped plan snapshot table in a separate milestone.

## Calculation inputs

Required fields are `currency`, `monthly_take_home_income`, `monthly_essential_expenses`, `existing_monthly_debt_payments`, `requested_amount`, and `planning_priority`. Require the user to confirm currency and use one currency throughout; V1 can accept INR only if the form clearly asks the user to confirm that entered amounts are rupees. No conversion is performed. Expenses exclude debt payments. Existing debt payments include all active monthly EMIs, card minimums, and other recurring credit payments. Explicit zero means the user confirmed none.

Optional fields are `monthly_gross_income`, `total_outstanding_debt`, `liquid_savings`, `monthly_savings_goal`, `loan_purpose`, `application_id` (for owned application prefill only), `as_of`, `annual_rate_percent`, and selected `terms_months`. A missing savings goal stays unknown; zero must be explicitly supplied to mean no monthly savings allocation. Defaults: rate 12% nominal annual, terms `[12, 24, 36, 48, 60]`; both are explicit editable planning assumptions, not product pricing. If gross income is missing, label the ratio "debt payments / take-home income" and do not call it DTI.

## Formulas

Let `I` be monthly take-home income, `G` gross monthly income when supplied, `E` essential monthly expenses, `D` existing monthly debt payments, `S` the user's optional monthly savings goal (zero only when the user explicitly enters zero), `P` principal, `n` term months, and `a` nominal annual rate as a decimal.

1. Convert `annual_rate_percent` to decimal `a = annual_rate_percent / 100`, then monthly rate `r = a / 12`.
2. Proposed EMI: if `r = 0`, `EMI = P / n`; otherwise `EMI = P × r / (1 − (1 + r)^−n)`.
3. Total repayment: `EMI × n`. Estimated interest: `max(0, total repayment − P)`. Fees, taxes, insurance and rate changes are excluded unless a future version explicitly models them.
4. Existing debt burden: `D`. Current conventional DTI: `D / G` only if gross monthly income is supplied; otherwise show `D / I` with its proper label.
5. Proposed DTI: `(D + EMI) / G` only when `G` is supplied. Also show proposed debt-service ratio `(D + EMI) / I` so the take-home cash-flow basis remains visible.
6. Residual monthly income: `I − E − D − EMI`. If the user supplies a monthly savings goal `S`, goal-adjusted residual is `residual − S`; if they do not, keep it `null` and do not silently treat unknown as zero.
7. Additional EMI headroom after savings goal: `max(0, I − E − D − S)` when `S` is known; otherwise return it as unknown. Also return pre-goal headroom `max(0, I − E − D)`. This is arithmetic capacity against the user's stated budget, not a safe lending limit. If asked, estimated principal capacity for term `n` is headroom times the annuity factor: `headroom × (1 − (1+r)^−n) / r` (or `headroom × n` at zero rate).
8. Savings buffer: if both `liquid_savings` and `E > 0` are known, `liquid_savings / E` months of essential expenses. Report separately; do not treat liquid savings as recurring income.

### Stress test

Run four cases: no shock, and take-home income reduced by 10%, 20%, and 30%. For each, `I_s = I × (1 − shock)`, while expenses, current debt payments, proposed EMI and savings goal stay fixed. Return stressed goal-adjusted residual and debt-service ratio `(D + EMI) / I_s`. State that fixed costs are held constant; real expenses and obligations may also change.

### Indicative affordability score

If monthly income and essential expenses are supplied, return an explainable **Planning Fit Score (0–100)**. It is a UX summary, never an approval score:

- Burden component (60 points): let `q = (D + EMI) / I`. Score 60 when `q ≤ 20%`; linearly reduce from 60 to 0 between 20% and 40%; score 0 at or above 40%.
- Residual component (40 points): let `m = residual_monthly_income / I`, before any optional savings goal. Score `40 × clamp(m / 30%, 0, 1)`. Show whether the residual also meets the user's savings goal separately.
- Final score is their sum, rounded to the nearest integer. Missing required inputs means no score, not zero. A missing savings goal stays unknown and does not alter the score; disclose that goal-fit is unavailable.

The 20% and 40% reference points reuse the current UI's illustrative thresholds; they are not empirically validated, regulatory limits or lender policy. Show the component values and score version. A negative residual or a high payment burden is shown directly even if a rounded score looks less concerning. Missing savings-goal data does not lower or inflate the score; it only makes goal-fit unavailable.

## Proposed request/response contract

### `POST /api/v1/planner/plan`

Cookie-authenticated `USER` role; require existing CSRF and same-origin mutation handling. The endpoint verifies ownership if `application_id` is included but still requires confirmation of planner-specific cash-flow values. It never loads a model or changes an application/prediction.

Request fields (Pydantic strict, extra fields forbidden):

```json
{
  "currency": "INR",
  "application_id": null,
  "as_of": "2026-10-04",
  "monthly_take_home_income": "120000.00",
  "monthly_gross_income": "150000.00",
  "monthly_essential_expenses": "45000.00",
  "existing_monthly_debt_payments": "18000.00",
  "total_outstanding_debt": "420000.00",
  "liquid_savings": "300000.00",
  "monthly_savings_goal": "10000.00",
  "requested_amount": "500000.00",
  "annual_rate_percent": "12.00",
  "terms_months": [12, 24, 36, 48, 60],
  "planning_priority": "BALANCED",
  "loan_purpose": "HOME_IMPROVEMENT"
}
```

The example is illustrative only. Amounts are finite nonnegative `Decimal`s bounded by product validation; income and requested amount must be positive. Term list must be unique and bounded to supported choices. Reject impossible percentages, negative obligations, unknown currency, and unsupported terms. Do not reject a budget deficit; return it as a clear warning.

Response contains `calculation_version`, currency/as-of/assumptions, input coverage flags, current debt burden, conventional DTI only when gross is known, proposed scenario metrics, residuals, headroom, optional savings-buffer months, Planning Fit Score/components, stress rows for every term, ranked scenarios, and warnings. Every scenario contains term, assumed APR, EMI, total repayment, estimated interest, current/proposed debt ratios, residual before/after savings goal, affordability score, four stress rows, rank, and rank explanation.

Response shape (values below are illustrative):

```json
{
  "calculation_version": "borrowing-planner-v1",
  "currency": "INR",
  "as_of": "2026-10-04",
  "inputs_basis": "USER_DECLARED",
  "existing_debt_burden_monthly": "18000.00",
  "current_dti": 0.12,
  "proposed_debt_to_income_ratio": 0.2307,
  "residual_monthly_income": "40392.85",
  "goal_adjusted_residual": "30392.85",
  "additional_emi_headroom": "47000.00",
  "savings_buffer_months": 6.67,
  "planning_fit_score": 73,
  "score_components": {"payment_burden": 33, "residual_cash_flow": 40},
  "stress": [{"income_drop_percent": 20, "stressed_residual_after_goal": "6392.85"}],
  "scenarios": [{
    "term_months": 36, "annual_rate_percent": "12.00", "emi": "16607.15",
    "total_repayment": "597857.40", "total_interest": "97857.40",
    "residual_after_loan": "40392.85", "goal_adjusted_residual": "30392.85",
    "fits_stated_budget": true, "rank": 1,
    "rank_explanation": "Balances monthly room with estimated total interest."
  }],
  "warnings": ["Illustrative rate; not a lender offer.", "Inputs are user-declared and unverified."]
}
```

The real response should include each stress case for every scenario; the short example omits repetitive rows for readability. If gross income is absent, return `current_dti` and `proposed_debt_to_income_ratio` as `null` and provide explicitly named take-home payment ratios instead. If a savings goal is absent, `goal_adjusted_residual`, savings-goal fit, and goal-specific ranking state are `null` rather than silently assuming zero.

V1 has no GET/list/history endpoint because results are not stored. User can rerun scenarios with edited inputs. Saved history/export is a later scope requiring a new table and retention/delete policy.

## UI/UX proposal

Add a user-only **Borrowing Planner** navigation entry. Start with a short form and transparent definitions: take-home income, essential expenses excluding debt, current monthly debt payments, optional gross income/liquid savings/savings target, requested amount, editable rate assumption, term choices and planning priority. Prefill application values as suggestions and make the user confirm them. Clearly identify each value as user-entered, application-prefilled, or unknown.

Show a cash-flow summary (income → expenses → existing obligations → proposed EMI → residual), existing and proposed DTI/payment ratios with their denominators, affordability component breakdown, and stress chart for 0/10/20/30% income drops. Use scenario comparison cards/table for EMI, total interest, residual and stress outcome. Mark scenarios that miss the user-stated minimum monthly buffer. Provide a plain-language "Why this ranks first" explanation. Keep risk probability and Financial Health Score in a separate panel; do not blend them into affordability.

Every view states: "Illustrative planning estimate, not a loan offer or eligibility decision. Rate and currency are user-confirmed assumptions; fees and lender terms may differ." Accessible labels, keyboard controls, responsive charts and a non-chart data table are required.

## Limitations and guardrails

- User-entered finances are not independently verified; missing values stay unknown.
- Gross/net income definitions vary; DTI is only named when gross monthly income was explicitly entered.
- An EMI ratio alone does not establish affordability; household obligations and irregular spending may be incomplete.
- Stress testing is deterministic sensitivity analysis, not a forecast.
- The score/ranges and 12% default are UX assumptions, not lending standards.
- Historical Installment Intelligence and model predictions are context only and are not inputs to loan ranking.
- Do not recommend a scenario as approved, eligible, offered, or safe. A scenario can be "fits the stated budget" or "exceeds the stated budget" only.

## Implementation roadmap (future milestone)

1. Freeze the request/response contract and calculation version; define supported bounds, currency confirmation and unknown-value behavior.
2. Implement pure Decimal-based amortization, residual, DTI, stress and score calculations with small meaningful tests for zero rate, zero debts, deficit, missing gross/savings fields, term ordering and limits. Keep this outside Lite/Full feature transformations.
3. Add the authenticated CSRF-protected stateless endpoint. If an application ID is supplied, use existing ownership enforcement and treat prefilled values as unconfirmed until the request explicitly confirms them. No migration for stateless V1.
4. Add a responsive user-only planner form and scenario table/chart, using existing currency formatting and API client. Keep risk assessment and Installment Intelligence separate.
5. Verify API auth/CSRF/ownership/invalid-payload paths, deterministic formulas, browser mobile layout, no changes to existing application/prediction/installment tests, and no model inference during planner calls.
6. Consider saved plans or live bureau/open-banking links only after explicit product scope, a dedicated schema/retention decision, consent, source timestamps and quality states.
