# Loan Recommendation Engine design

**Status:** design only; no model training or implementation.  
**Dependency:** Borrowing Planner formulas and user-confirmed inputs in [BORROWING_PLANNER_DESIGN.md](BORROWING_PLANNER_DESIGN.md).

## Purpose and source boundaries

Compare repayment terms for a user-requested principal and user-confirmed rate. The engine is deterministic amortization plus a visible ranking preference. It is not an underwriting model, eligibility service, personalized lender offer, or actual bank rate comparison. It does not consume Lite probability, FULL_RESEARCH_V1_NO_EXT, or Installment Intelligence metrics to rank terms.

Existing sources can prefill annual-income-labeled amount, requested amount and term from an owned application. The user must confirm amount/currency and supply current take-home income, essential expenses and existing monthly debt payments. Home Credit history files are not joined to the current user. No retraining is needed for arithmetic.

## Scenarios

Default terms are 12, 24, 36, 48 and 60 months, editable by user. Default APR is 12%, matching the current illustrative quote; label it as an assumption and allow edits. Future rate-range analysis may be added, but V1 should not imply the assumed rate is available from any lender.

For each term calculate monthly EMI with the standard amortizing-loan formula documented in the Planner design; total repayment is EMI times term; total interest is repayment less principal. Show exclusions (fees, taxes, insurance, variable pricing, payment timing and lender-specific rounding). Currency stays constant across inputs and results; no conversion.

Every scenario includes:

- EMI and its share of take-home income.
- Existing-plus-proposed monthly debt payments and DTI if gross monthly income was supplied; otherwise a clearly labeled take-home payment ratio.
- Residual monthly income before and after any user monthly savings goal.
- Total repayment and estimated interest.
- 0%, 10%, 20% and 30% take-home income stress results.
- Whether residual meets the user's stated buffer/savings target, with reason codes.

## Ranking logic

First compute all scenarios; never suppress a term because a generic lender threshold says it is ineligible. A scenario fits the stated budget when its residual after expenses, existing debt payments, new EMI and supplied monthly savings goal is nonnegative. If no savings goal was supplied, test only whether the residual before savings goal is nonnegative and label goal-fit as unknown. If at least one scenario fits, rank fitting scenarios ahead of non-fitting scenarios. If none fit, keep all visible, label that none fit the stated budget, and rank by least monthly shortfall before the chosen preference. Do not turn this rank into approve/reject.

For preference among fitting scenarios, compute two normalized 0–100 components across the displayed set:

- `monthly_room_score`: lower EMI receives the higher score.
- `interest_saving_score`: lower total interest receives the higher score.

Use min-max normalization: `monthly_room_score = 100 × (max_EMI − scenario_EMI) / (max_EMI − min_EMI)` and `interest_saving_score = 100 × (max_interest − scenario_interest) / (max_interest − min_interest)`. If a denominator is zero, assign 100 to every scenario on that component.

Preference weights:

| User priority | Monthly room | Interest saving |
|---|---:|---:|
| Lower EMI | 70% | 30% |
| Lower total interest | 30% | 70% |
| Balanced | 50% | 50% |

`rank_score = weighted sum`; ties break by (1) higher goal-adjusted residual, then (2) lower total interest, then (3) shorter term. If a component has zero spread across scenarios, assign equal component scores rather than divide by zero. Persist/display the score components so the user can understand every ordering. The ranking is relative to the currently displayed terms and changes if the user changes principal, rate or terms.

Example explanation: "36 months ranks above 24 months for your balanced preference because it leaves more monthly room while adding ₹X estimated total interest. The 60-month option has the lowest EMI but the highest total interest." Values are generated from the actual scenario calculations, not fixed prose.

## Contract and API

Use the Planner endpoint `POST /api/v1/planner/plan` and response; do not create a second source of truth or another scoring endpoint. A `scenarios` response array is sorted by `rank`, but also retains the original term order for charts. The response includes `ranking_policy_version`, weights, component scores, fit state, and a generated explanation per row. No database write is required for the stateless first version.

If user-save is later requested, add an owner-scoped immutable `borrowing_plans` record with request snapshot, response snapshot, calculation/ranking version, currency, `as_of`, timestamps and deletion/retention behavior. Do not treat `loan_quotes` as scenario storage: it belongs to an application version and currently records the illustrative application quote.

## UI/UX proposal

Show a clear comparison table with term, EMI, estimated total interest, total repayment, remaining monthly amount and stress result. Use a chart only as a companion to the accessible table. A preference selector changes the order and explains the updated reason. Include a toggle to compare total cost versus monthly room, and a warning when longer terms reduce monthly payment but increase total interest. Let users change principal, APR and terms and recalculate immediately through the authenticated planner API.

Use explicit badges such as **Fits the budget you entered** and **Above the budget you entered**. Avoid "recommended for approval", "eligible", "pre-approved", and "best offer". Put loan risk and affordability on separate panels. Keep admin read-only pages out of this flow.

## Acceptance rules for later implementation

1. No network call to the model and no change to prediction outputs.
2. Same validated inputs always yield the same scenarios and ranks for a given calculation version.
3. 0% APR, very short terms, zero debts/expenses, exact-zero residual, missing optional gross income, no-feasible-scenario, and identical-score ties have defined behavior.
4. API requires authentication/CSRF, validates ownership for application prefill, rejects invalid currency/amounts/duplicate terms, and preserves unknowns.
5. Each scenario gives its arithmetic and ranking explanation; all results identify assumptions and omitted fees.
