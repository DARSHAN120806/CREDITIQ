# Installment Intelligence V1 — implemented architecture

Updated 4 October 2026. Validation status is tracked in INSTALLMENT_V1_VALIDATION.md.

## Boundaries

This is a deterministic repayment analytics module, not a trained model. Existing Lite source, contracts, artifact, prediction APIs, decisions and model registry are unchanged. mode=RESEARCH_ONLY and release_ready=false remain unchanged. No historical Kaggle borrower is linked to an actual user. No raw dataset scan/import occurs in the application.

The backend calls the existing pinned creditiq_ml.features.installments_features function without editing it. The supplied effective schedule and allocated payment events are projected into its relative-day representation for retrospective aggregate calculations. DAYS_AVAILABLE=0 in that projection means included in the supplied as-of snapshot; it is NOT evidence of historical availability. The result explicitly records historical_availability_verified=false and independently_verified=false. This adapter must not be used to unlock Full-model provenance gates or training. Additional installment-level calculations use decimal money and the same 0.01 completion tolerance, with regression checks against the pinned aggregates.

## Data flow

Owned JSON/form input -> Pydantic cross-record validation -> payment-identity deduplication -> cutoff/window selection -> existing aggregate reconciliation plus per-installment/temporal metrics -> immutable import/schedules/payments/analysis + audit event in one transaction -> owned read APIs and read-only admin aggregates.

An import is one effective cash-loan schedule snapshot. Schedule versions must be resolved by the supplier; duplicate account/installment keys are rejected even if version differs. Payments are allocated to one installment by account_ref/installment_ref. Split payments use separate event_ref values. Identical event replays are deduplicated; conflicting event identities fail. V1 does not split one event across obligations, reconcile reversals, collect original documents or fetch bank data. Corrected histories create new imports; there are no mutation/delete APIs.

Source kinds: USER_DECLARED for a user's records; DEMO for explicitly labeled examples. Currency is INR or unspecified XXX; demos require XXX and display units. No currency conversion. Supabase connection settings are untouched.

## Storage

- installment_imports: user FK, owner-scoped idempotency key, normalized content SHA-256, label, source/currency, as-of/window dates, coverage.
- installment_schedules: import FK, account/installment identity, effective version, due date, positive scheduled amount. One effective installment per import/account/reference.
- installment_payments: import FK and composite FK to schedule within that same import, unique event reference per import, payment date and nonnegative amount.
- installment_analyses: import FK, calculation version and immutable JSON metrics/timeline/record snapshot; unique import/version.

Reuse users, sessions, RBAC, audit_events and existing model storage unchanged. Do not force standalone history into application-bound source_snapshots. Four new tables bring metadata to 28. Alembic revision 20261003_0003 follows 0002. Existing immutable-record trigger protects all four. Runtime role receives SELECT/INSERT only through the existing local grant operator. Remote database operators must apply migration and equivalent grants with their normal owner/migration credentials.

## Metric contract

Window includes due dates >= window_start and strictly < as_of. Due-today and future installments are excluded from overdue denominators. Payments after as_of are stored but ignored for that snapshot. Observation dates are UTC date boundaries; analysis is retrospective, not a point-in-time predictive backtest.

- ON_TIME: complete on/before due date; LATE: completed after due date.
- MISSED: past due and no positive payment by cutoff, conditional on complete declared payment coverage.
- PARTIAL: some payment but not complete at cutoff.
- UNKNOWN: incomplete payment coverage; absence/timing cannot be established.
- Discipline: 100 * on-time / eligible due count. Headline score requires complete declared schedules/payments, >=6 eligible installments and >=90 days between observed due dates. This eligibility rule is a product minimum, not statistical confidence.
- On-time percentage: same rate; may describe a limited supplied schedule, with coverage visible.
- Payment Reliability: sum of paid-by-due amounts capped separately at each scheduled amount / sum scheduled amounts, expressed as a percentage.
- Average Late Delay: positive delays among late-completed installments only; null if none.
- Worst Delay: maximum completed delay or outstanding overdue age.
- Consistency: population standard deviation of completed-payment signed delays, in days; requires at least two. Less variation does not necessarily mean punctual payment.
- Recovery: share of overdue installments cured within 30 days, using only due dates with >=30 days of follow-up. Monthly cohorts carry their denominators.
- Improvement: recent 90-day on-time percentage minus preceding 90-day percentage; needs complete declared coverage, full 180-day window and >=3 observations per period. Otherwise unavailable.
- Null means unavailable/not applicable, never automatically zero. Coverage is self-reported or demonstration; never independently verified.

## API inventory

POST /api/v1/installment-history/imports: USER only, CSRF and UUID Idempotency-Key. Returns 201 AnalysisView. Atomic normalization/storage/calculation/audit. Same normalized payload/key returns same snapshot; a different payload with the same key returns 409. Input maximum 500 schedules, 2000 payments, 1 MB request body.

GET /api/v1/installment-history/imports/{id}: owned immutable analysis/source summary.
POST /api/v1/installment-analyses: USER + CSRF, {import_id}; returns the already-created V1 immutable analysis. Recalculation/version editing is deliberately unavailable.
GET /api/v1/installment-analyses: owner-scoped, limit 1..50 (default 10), offset >=0.
GET /api/v1/installment-analyses/{id}: owned result.
GET /api/v1/installment-analyses/{id}/timeline: owned timeline and coverage.
GET /api/v1/admin/installment-analyses: ADMIN read-only paginated list.
GET /api/v1/admin/installment-analyses/{id}: ADMIN read-only detail.
GET /api/v1/admin/installment-statistics: total/personal/demo analysis counts and mean of scored personal analysis snapshots. This is analysis-weighted, not a unique-borrower portfolio score; demo scores excluded.

AnalysisView: id, import_id, created_at, calculation_version, label, source_kind, currency, as_of, window_start, metrics, coverage, timeline, installments, aggregates. Non-owned IDs return 404, unauthenticated reads 401, CSRF/wrong role 403, malformed input 422, body overflow 413. All responses on these paths are no-store. Existing mutation limits/auth behavior are unchanged; only history import has a 1 MB body allowance.

## Frontend

/financial-analysis replaces Coming Soon with manual history entry, JSON import, a downloadable example schema, labeled demo action, saved analyses and all metrics. Dashboard adds a separately labeled latest repayment preview. /admin/installments is read-only. Recharts supplies stacked monthly outcomes and on-time/recovery lines; tables expose exact accessible values. Existing result, application, auth and admin pages remain.

Future work: verified bank/document ingestion, card-specific reconciliation, multiple-event allocation, reversal handling and optional trained behavior/Full models. No retraining, deployment or notifications are part of V1.
