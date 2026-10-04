# CreditIQ research frontend

Next.js 15.5.27 / React / TypeScript / Tailwind. Browser calls /api/v1 on the same origin; Next rewrites to API_ORIGIN (default http://127.0.0.1:8000). No browser database credentials or Supabase SDK. The existing FastAPI cookie authentication remains authoritative.

Run from apps/web: `npm ci`, `npm run dev`. Start the existing FastAPI service separately from services/api with `.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000`. Open http://127.0.0.1:3000. Retain the configured service .env; allow the frontend origin, and use non-Secure cookies only for loopback HTTP. The configured Lite artifact and existing ML source must remain available under ml/. No training runs on startup.

Pages: /login, /register, /dashboard, /applications/new, /applications, /applications/{id}, /applications/{id}/result, /profile; /admin/login, /admin, /admin/users, /admin/users/{id}, /admin/applications, /admin/applications/{id}, /admin/statistics. Root opens user sign-in. All non-public pages check /me; ADMIN routes also check role. Backend authorization is authoritative.

The API helper obtains signed CSRF for mutations, sends HttpOnly cookies, serializes mutations/refresh within the tab and across supporting browsers through Web Locks, and refreshes expired access once. Tokens are not stored in localStorage. Application retries reuse a UUID key while the form payload is unchanged. Registration never creates an admin; use the existing trusted administrator CLI.

Amounts are XXX research units, annual income and monthly payment. The fixed 12% annual rate/no-fee quote is illustrative. Results show sandbox recommendations and explicitly never claim lending approval/rejection. Advanced explanations, editing, manual reviews and deployment are outside this prototype.

Validation: `npm run typecheck`, `npm run build`, `npm test`. Browser tests require the backend to use only the disposable creditiq_migration_test database, a frontend at port 3000 and the test-only browser-admin@example.com account with the password in tests/prototype.spec.ts. Never create that known test account in a deployed or real-user database. Tests use installed Edge headlessly. Follow PROTOTYPE_VALIDATION.md for verified results and fixture setup/cleanup details. Do not run backend destructive migration tests concurrently with browser tests.

Installment Intelligence V1 is implemented at /financial-analysis and /admin/installments. Manual cash-loan history, JSON imports, labeled examples, immutable saved analyses and charts are available. See ../../INSTALLMENT_V1_VALIDATION.md and ../../INSTALLMENT_ANALYSIS_ARCHITECTURE.md. For isolated browser tests, set PLAYWRIGHT_BASE_URL; CREDITIQ_WEB_DIST_DIR selects an optional separate Next build directory (default remains .next).
