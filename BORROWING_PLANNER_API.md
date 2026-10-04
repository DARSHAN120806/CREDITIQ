# Borrowing Planner API

**Status:** Implemented V1. This authenticated, stateless calculator is independent of Lite risk scoring, Financial Health Score and Installment Intelligence. It performs no model inference and writes no application data.

## `POST /api/v1/planner/plan`

Authentication: existing user session/JWT and `USER` role. Cookie-authenticated requests must pass the existing CSRF check. If `application_id` is provided, the server checks that it belongs to the caller; it does not copy or persist application data.

Request JSON (INR only; amounts are rupees, Decimal precision to paise):

| Field | Required | Definition |
|---|---:|---|
| `currency` | yes | Must be `INR`. |
| `monthly_take_home_income` | yes | Positive user-declared monthly net income. |
| `monthly_essential_expenses` | yes | Nonnegative; excludes debt payments. |
| `existing_monthly_debt_payments` | yes | Nonnegative monthly EMIs and recurring debt payments. Explicit zero means none. |
| `requested_amount` | yes | Positive proposed principal. |
| `planning_priority` | no | `LOWER_EMI`, `LOWER_TOTAL_INTEREST`, or `BALANCED`; default `BALANCED`. |
| `monthly_gross_income` | no | Positive gross monthly income; enables DTI fields. |
| `total_outstanding_debt` | no | Nonnegative current principal balance, informational. |
| `liquid_savings` | no | Nonnegative; savings-buffer months divide this by essential expenses. |
| `monthly_savings_goal` | no | Nonnegative; omitted means unknown, zero means explicitly no allocation. |
| `annual_rate_percent` | no | 0–1000 nominal annual percent; default 12. Planning assumption, not a lender quote. |
| `terms_months` | no | Unique integers 6–360, 1–12 terms; default `[12,24,36,48,60]`. |
| `application_id` | no | UUID for ownership validation only. |
| `loan_purpose` | no | Optional label, max 120 chars; informational only. |
| `as_of` | no | Date, defaults to UTC current date; future dates rejected. |

Unknown fields are rejected. Amounts must be finite, nonnegative where applicable, and no more than ₹1,000,000,000.

Response includes `calculation_version`, `mode=RESEARCH_ONLY`, `release_ready=false`, confirmed input basis, current debt burden, current DTI (null without gross income), take-home payment ratio, optional outstanding debt/savings, monthly expenses/savings target, EMI headroom (null when savings goal is unknown), savings-buffer months, priority/weights, warnings and ranked scenarios.

Each scenario includes term, EMI, total repayment/interest, current and proposed ratios, residual and goal-adjusted residual, headroom, Planning Fit Score and components, budget-fit flags, stress cases at 0/10/20/30% income reduction, normalized monthly-room and interest-saving scores, weighted rank score, rank and human-readable explanation. Monetary response values are decimal strings rounded to two places; ratios/scores are numeric.

Validation errors use the existing FastAPI/Pydantic 422 format. Missing/invalid authentication returns existing 401/403 behavior; CSRF failure is 403; a supplied non-owned application returns 404.

## Calculation boundaries

EMI uses the standard amortizing-payment formula with a separate zero-rate case. Total interest is rounded-payment total repayment minus principal, floored at zero. Residual income subtracts essential expenses, current debt payments and proposed EMI. DTI uses monthly gross income only when supplied. Stress tests reduce take-home income and keep expenses/debt payments fixed. Scenario ranking uses per-request normalized monthly room and interest-saving scores with the selected priority weights, then budget-fit ordering and deterministic tie-breaks. The response labels estimates as illustrative and unverified.
