# Borrowing Planner data feasibility

**Assessment date:** 4 October 2026  
**Scope:** data and existing application only; no implementation or model changes.  
**Decision:** a transparent cash-flow planner is feasible if missing present-day finances come from the user. The repository does not contain verified current expenses, obligations, savings, or live bureau connections.

## What the repository actually has

The eight Home Credit CSVs under `ml/data/raw/DATASET_CREDITIQ/` are a historical research dataset. They are not connected to a signed-in CreditIQ user. A row keyed by `SK_ID_CURR` is a dataset applicant, not an authenticated application owner. Do not join a live user to those records or present their historical values as that user's current finances.

The current application form collects age, employment details, annual-income-labeled amount, requested principal, loan term, education, household size, dependents and optional occupation/housing. `AMT_INCOME_TOTAL` was treated as annual only under a research assumption; gross/net basis is unverified. `AMT_CREDIT` is the current requested amount in the research source. `AMT_ANNUITY` was treated as monthly, but the live prototype creates an illustrative annuity from the requested amount, selected term and a fixed 12% annual rate. It is not an existing EMI and is not a bank offer. The 22-feature `FULL_RESEARCH_V1_NO_EXT` contract is an application-record snapshot only; it has no monthly expenses, current liabilities, current debt payments, savings or financial goals, and it is not served by the app.

## Available inputs by purpose

| Planner need | Repository evidence | What can safely be used now | Limit |
|---|---|---|---|
| Affordability | Current app's annual-income-labeled field, requested amount, term and illustrative EMI | Prefill income, principal and term for user confirmation; calculate current proposed EMI | Income periodicity and gross/net basis are not verified. Existing UI explicitly excludes expenses and other EMIs. |
| Debt burden | `bureau.csv` has historical active status, debt, overdue amounts, credit limits and dates; card/POS files have balances and delinquency fields | No borrower-specific present-day amount from these files | Kaggle rows are not a live user feed; currentness, matching, source authorization and point-in-time availability are unverified. |
| Repayment capacity | User-submitted installment schedule/payment history and its analysis | Show historical repayment behavior as separate context; use user-declared current monthly obligations in the planner | Installment V1's discipline, reliability, timing, recovery and missed/late counts are retrospective and unverified. It does not report a verified total current EMI or full outstanding principal. |
| Loan scenarios | Requested principal, selected term, current illustrative 12% rate | Recalculate amortization at explicit user-selected assumptions | No lender pricing, fees, eligibility or actual offer exists. |
| Household context | Application has household size/dependent children; training data also has demographics | Optional context for user display | It does not measure living costs or disposable income. Avoid implying it does. |

## Source-by-source review

| Dataset | Relevant fields present | Planner opportunity | Current constraint / retraining |
|---|---|---|---|
| `application_train.csv` | `AMT_INCOME_TOTAL`, `AMT_CREDIT`, `AMT_ANNUITY`, `AMT_GOODS_PRICE`, household/dependent and employment fields | Research analysis; existing application can prefill user-confirmed income, amount and term | Historical labeled application rows, not current user data; annual/gross/net and currency assumptions persist. Calculations only; no retraining for planner math. |
| `application_test.csv` | Similar application fields, no `TARGET` | None for a signed-in user's personal finances | Competition holdout with no labels; not a user registry. |
| `bureau.csv` | `CREDIT_ACTIVE`, `AMT_CREDIT_SUM_DEBT`, `AMT_CREDIT_SUM_OVERDUE`, `AMT_CREDIT_SUM_LIMIT`, credit dates/types | Research outstanding exposure/delinquency aggregates; a future consented, current bureau response could prefill debt balances and monthly dues | Historical file does not prove a current balance or connect to a CreditIQ account. Dataset-derived risk features require feature engineering and retraining if added to risk scoring; calculator-only prefill does not. |
| `bureau_balance.csv` | Monthly `MONTHS_BALANCE` and `STATUS`, linked by `SK_ID_BUREAU` | Research delinquency timeline and status frequencies | Bureau-to-account identity and cutoff/source availability gates remain unresolved. Feature engineering; retraining only if used by a predictive model. |
| `previous_application.csv` | Prior application amount, credit, annuity, term, status, decision recency and refusal reason | Research borrowing-frequency/refusal and past payment-quote analytics | Prior applications are not necessarily current open debts; not a present liability register. Feature engineering; retraining only if used for prediction. |
| `POS_CASH_balance.csv` | Monthly contract status, DPD, future installments, previous-loan ID | Research cash-loan/point-of-sale repayment trend | Historical snapshots and application-time availability are not production verified. Feature engineering; model use requires retraining. |
| `credit_card_balance.csv` | Monthly balance, limit, payments, minimums, DPD and drawings | Research revolving utilization and minimum-payment behavior | Does not establish a current user's current card balance. Feature engineering; model use requires retraining. |
| `installments_payments.csv` | `SK_ID_CURR`, previous-loan ID, installment number/version, due/payment day offsets, scheduled/payment amounts | Research repayment features after reconciliation | Raw file has no payment-event identity or `DAYS_AVAILABLE`, and effective schedule reconciliation is unresolved in the training data. Not suitable for current obligations or user-level automatic import. Feature engineering; model use requires retraining. |

## Inputs genuinely missing and recommended form

Collect current cash-flow values from the user, with a visible as-of date and explicit currency. The initial form should require:

| Input | Type / validation | Why required |
|---|---|---|
| `currency` | User-confirmed ISO code; V1 may allow INR only and must state no conversion occurs | The Kaggle source currency is unspecified and current application storage uses `XXX`; a rupee symbol has been presentation-only. |
| `monthly_take_home_income` | Positive decimal, after tax and regular deductions | Base for residual cash flow and payment burden; do not silently derive it from assumed annual gross income. |
| `monthly_essential_expenses` | Nonnegative decimal, excluding all debt/loan payments | Needed for residual monthly income. Include housing, food, utilities, transport, healthcare and essential support. |
| `existing_monthly_debt_payments` | Nonnegative decimal; explicit confirmation that zero means no current debt payments | Existing EMIs and recurring debt servicing are not in the app form. Include card minimums and other credit obligations. |
| `requested_amount` | Positive decimal | Scenario principal; can be prefilled from an existing application but user confirms. |
| `planning_priority` | `LOWER_EMI`, `LOWER_TOTAL_INTEREST`, or `BALANCED` | Makes scenario ordering reflect the user's goal rather than hidden weights. |

Optional fields improve context without being fabricated: `monthly_gross_income` (only for conventionally labeled DTI), `total_outstanding_debt` (balance exposure, distinct from monthly payment), `liquid_savings`, `monthly_savings_goal`, loan purpose/goal, and an as-of date. Offer a clear "I don't know" state for optional values. A zero obligation is a user assertion, not a missing value.

For an existing application, prefill its user-entered income, principal and term, but require the user to confirm or change them and add the missing household cash-flow fields. The existing annual income may be shown as a reference (`annual_income / 12`) only after the user confirms the period and whether it is take-home or gross. Do not carry `AMT_ANNUITY` forward as an existing EMI.

Installment Intelligence can optionally show the user's own declared-history metrics alongside the planner: repayment discipline, on-time percent, reliability, delays, late/missed/partial counts, recovery trend, and coverage status. These are contextual history, not inputs to a verified present debt total. V1 requires the user to enter current monthly debt payments independently.

## Recommendation

Ship the first planner as user-entered, as-of cash-flow arithmetic with explicit assumptions. Keep historical risk outputs and self-reported repayment history in separate cards. Do not use Kaggle rows to populate a person's financial profile. A future verified-bureau/open-banking integration could reduce user entry and improve debt exposure, but needs consent, secure connector work, source timestamps, coverage states, and data-quality handling before it can be treated as current.

## Pre-implementation contract checks

- The static `FULL_RESEARCH_V1_NO_EXT.json` reports 22 `feature_definitions`, but its separate `features` array still lists the original 28 names including all six removed EXT_SOURCE entries. Its training run used the 22 definition names, but consumers must not treat this inconsistent JSON as an authoritative feature list until a separate contract correction is reviewed. This planner does not depend on that model.
- The current application API still loads Lite only. `FULL_RESEARCH_V1_NO_EXT` is not a live planner or scoring source; its bureau-inquiry features are not collected by the application request form.
- The backend stores application/quote currency as `XXX`; the frontend's INR formatting is a display convention without conversion. A planner must explicitly collect/confirm currency and keep planner values internally consistent before displaying INR.
