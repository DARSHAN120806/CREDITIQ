# CreditIQ research frontend

Next.js 15.5.27 / React / TypeScript / Tailwind. Browser calls /api/v1 on the same origin; Next rewrites to API_ORIGIN (default http://127.0.0.1:8000). No browser database credentials or Supabase SDK. The existing FastAPI cookie authentication remains authoritative.

Run from apps/web: `npm ci`, `npm run dev`. Start the existing FastAPI service separately from services/api with `.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000`. Open http://127.0.0.1:3000. Retain the configured service .env; allow the frontend origin, and use non-Secure cookies only for loopback HTTP. The configured Lite artifact and existing ML source must remain available under ml/. No training runs on startup.

Pages: /login, /register, /dashboard, /applications/new, /applications, /applications/{id}, /applications/{id}/result, /profile; /admin/login, /admin, /admin/users, /admin/users/{id}, /admin/applications, /admin/applications/{id}, /admin/statistics. Root opens user sign-in. All non-public pages check /me; ADMIN routes also check role. Backend authorization is authoritative.

The API helper obtains signed CSRF for mutations, sends HttpOnly cookies, serializes mutations/refresh within the tab and across supporting browsers through Web Locks, and refreshes expired access once. Tokens are not stored in localStorage. Application retries reuse a UUID key while the form payload is unchanged. Registration never creates an admin; use the existing trusted administrator CLI.

Amounts are XXX research units, annual income and monthly payment. The fixed 12% annual rate/no-fee quote is illustrative. Results show a read-time affordability overlay alongside the historical model estimate and never claim lending approval/rejection. Advanced explanations, editing, manual reviews and deployment are outside this prototype.

Validation: `npm run typecheck`, `npm run build`, `npm test`. Browser tests require the backend to use only the disposable creditiq_migration_test database, a frontend at port 3000 and the test-only browser-admin@example.com account with the password in tests/prototype.spec.ts. Never create that known test account in a deployed or real-user database. Tests use installed Edge headlessly. Follow PROTOTYPE_VALIDATION.md for verified results and fixture setup/cleanup details. Do not run backend destructive migration tests concurrently with browser tests.

Installment Intelligence V1 is implemented at /financial-analysis and /admin/installments. Manual cash-loan history, JSON imports, labeled examples, immutable saved analyses and charts are available. See ../../INSTALLMENT_V1_VALIDATION.md and ../../INSTALLMENT_ANALYSIS_ARCHITECTURE.md. For isolated browser tests, set PLAYWRIGHT_BASE_URL; CREDITIQ_WEB_DIST_DIR selects an optional separate Next build directory (default remains .next).

## Model limitations

The Lite model uses form-available features and derived ratios only; it does not use EXT_SOURCE or bureau inputs. Application payments are generated at a fixed 12% annual rate, whereas training used recorded annuities. Under the annual-income/monthly-annuity assumptions, the training payment-to-monthly-income median is about 207%. The outcome horizon is unverified. The model estimate describes historical dataset patterns, not personal affordability or loan approval.

Results, history and dashboard analytics compute an affordability overlay at read time from saved income and quoted EMI; stored predictions and policy decisions are unchanged. Risk Level is the worse of the historical model band and EMI burden (Low at <=20%, Moderate at >20–40%, High above 40%). Affordability score is 100 through 20%, decreases linearly to 50 at 40%, then to 0 at 100%, and remains 0 above 100%. It excludes existing debts and living costs. Missing financial details display unavailable rather than a fabricated score.

MODEL_BAND_CUTOFFS in lib/finance.ts records the calibrated probability percentiles 33/66 (0.050386401618192744 / 0.08841984944398855), computed using NumPy's default linear interpolation on the 27,822 reserved policy-validation IDs in the pinned Lite run 20261002T140817Z-045430a7. Source: ml/real_data_output/processed/features_lite_37489e0c27416f0e.parquet and the run's splits.json. This cohort was held out from classifier/calibrator fitting; the final test cohort was not used to choose bands. These relative display bands are not approved lending thresholds. mode=RESEARCH_ONLY; release_ready=false.
