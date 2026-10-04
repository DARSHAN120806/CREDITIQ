# Borrowing Planner V1 Validation

**Status:** implementation validation; RESEARCH_ONLY, `release_ready=false`.

## Scope and boundaries

- Added one authenticated user endpoint, pure Decimal calculation service, strict request/response schemas and a responsive user planner page.
- No model artifact, ML training, Lite behavior, Installment Intelligence behavior, authentication implementation, migration, existing prediction API, or stored application/prediction records were changed.
- Application link is an optional ownership check only. Planner endpoint writes no rows and does not invoke/load an estimator.
- Inputs are user-declared and unverified. Currency is INR as entered by the user. Planner results are not loan offers, underwriting decisions, or validated financial advice.

## Automated validation

- Full backend suite: **115 passed**, including planner calculation, validation, ranking, authenticated endpoint no-model/no-write and CSRF tests. The endpoint test used the isolated `creditiq_migration_test` database; no development database was used.
- The backend suite emitted one existing Starlette/httpx TestClient deprecation warning; no failures.
- Frontend TypeScript check: passed.
- Planner browser journey: **1 passed**; submitted inputs, checked rendered scenarios and captured desktop/mobile screenshots.
- Next.js production build: passed (Next.js 15.5.27; production compilation, type validation and static page generation completed).
- Full backend suite: **115 passed**.

## Visual artifacts

- `apps/web/test-results/borrowing-planner-desktop.png`
- `apps/web/test-results/borrowing-planner-mobile.png`

Screenshots are captured by the passing Playwright test. Desktop and mobile layouts were visually inspected after the mobile navigation layout correction. The comparison tables remain horizontally scrollable on narrow screens.

## Remaining limitations

- No history or save-plan feature; the endpoint is stateless.
- Planning Fit Score and ranking are transparent research heuristics. They have not been calibrated against consumer outcomes.
- APR, fees, expenses and debt values are user-supplied; interest/fees/taxes/insurance and lender pricing variability are not modeled.
- Stress scenarios assume expenses and existing debt payments remain fixed as take-home income falls.
- Gross income is optional; conventional DTI is withheld when absent. Savings-goal-adjusted values remain null when the goal is omitted.
