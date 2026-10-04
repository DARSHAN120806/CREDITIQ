# Milestone 3 authentication and authorization

Verified 3 October 2026. FastAPI/SQLAlchemy/PostgreSQL implementation, using the existing users, user_profiles, auth_sessions and audit_events tables. Backend version 0.3.0, mode=RESEARCH_ONLY, release_ready=false. No ML models are loaded and no lending decisions are made.

## Setup and operations

Use the existing service-local virtual environment and ignored .env. Do not overwrite this workspace's configured credentials. New environments need the database migrations, an independently generated JWT secret (at least 32 bytes; recommend secrets.token_urlsafe(48)), explicit browser origins, and database credentials. .env.example lists every setting. Never commit or print operational secrets in diagnostics.

Run in services/api (PowerShell):

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
.\.venv\Scripts\python.exe -m scripts.local_db verify
.\.venv\Scripts\python.exe -m scripts.local_db upgrade
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

The local operator helper is restricted to this workspace's cluster. Other environments must provision their own migration/runtime roles. No migrations run during app startup. Revision 20261003_0002 adds three lookup indexes; the original revision and 24-table schema remain intact.

The local .env uses COOKIE_SECURE=false for loopback HTTP. Defaults use Secure cookies, and staging/production settings reject insecure cookies and non-HTTPS origins. A missing/short signing secret prevents application creation. Environment classification never promotes the research release.

## HTTP contract

All paths below have /api/v1 prefix. Authenticated requests use cookies; access/refresh credentials are never returned in JSON and Authorization-header bearer authentication is not implemented. Use credentials: include for browser requests and explicit allowed origins. A same-site HTTPS frontend/API topology is required by SameSite=Strict; cross-site hosting requires a separately reviewed design.

| Method | Path | Authentication and result |
| --- | --- | --- |
| GET | /auth/csrf | Public; 200 with csrf_token and signed CSRF cookie |
| POST | /auth/register | CSRF; email, password, full_name; 202 generic acknowledgement for new/duplicate address; no automatic login |
| POST | /auth/login | CSRF; email/password; 200 with public user fields, csrf_token and expires_in; access/refresh cookies |
| POST | /auth/refresh | CSRF and refresh cookie; 200 with rotated cookies and same response shape as login |
| POST | /auth/logout | CSRF; 204, revoke current family and clear cookies; works with expired access and valid refresh |
| GET | /me | Active access/session/account; 200 with id, email, full_name, role, permissions |
| GET | /auth/sessions | sessions:manage; 200 list of own active session id, created_at, expires_at, current |
| DELETE | /auth/sessions/{session_id} | CSRF and sessions:manage; 204 revoke owned family, 404 if unknown/not owned |
| POST | /auth/logout-all | CSRF and sessions:manage; 204 revoke all own sessions and clear cookies |

Obtain /auth/csrf before every mutation workflow; send its value in X-CSRF-Token and retain cookies. Every mutation requires an exact allowed Origin, even login and registration. Login/refresh return a replacement CSRF token bound to the new refresh token; use that replacement on subsequent requests. CSRF tokens expire after one hour and can be reissued through /auth/csrf. Do not store JWTs or refresh tokens in localStorage. Clients must serialize refresh across tabs and requests: replay detection deliberately revokes a family if an old refresh token is reused, including a duplicate retry after a lost successful response.

Errors: 401 authentication/expiry/replay, 403 CSRF or insufficient role/permission, 404 session not owned, 413 auth body over 16 KiB, 422 invalid payload, 429 throttled (Retry-After), 503 database unavailable. Responses omit passwords, token hashes and SQL details; auth responses are no-store. Public registration forbids extra fields, including role/permissions, and does not reveal duplicate account IDs. Email is validated and normalized to lowercase. Password creation requires 15–128 characters; login accepts 1–128 for future compatibility.

## Security and transaction behavior

- Argon2id: 64 MiB memory, time cost 3, parallelism 2, random salts; rehash on successful login when parameters change. Four simultaneous hash operations per worker bound hashing memory. Missing accounts use a dummy hash verification.
- JWT: HS256 only, issuer/audience/purpose/UUID claims validated, required exp/iat/nbf; default lifetime 15 minutes, never beyond the refresh family's absolute expiry. Secret rotation invalidates existing tokens; coordinated key rotation is later operational work.
- Refresh: 48 random bytes, SHA-256 hash stored, 30-day absolute family lifetime, rotation does not extend expiry. Revoked rows retained for reuse detection. All family changes lock the owning user before session rows; replay revocation commits before returning 401. At most ten active device sessions per user; new login revokes oldest overflow families.
- Access checks current DB account status, session revocation/expiry and current role/scopes on every request. Logout/rotation/revocation invalidates corresponding access tokens immediately on subsequent requests. Authorization is checked at request time; future sensitive business transactions must recheck authorization under their own transaction locks.
- HttpOnly access/refresh cookies, SameSite=Strict, no Domain. Secure mode uses __Host- cookie names and Path=/ to reject sibling-domain cookie injection. The signed CSRF cookie is readable, refresh-bound and also host-prefixed in Secure mode. HMAC purposes separate token binding and rate-limit identifiers.
- PostgreSQL advisory transaction locks and indexed immutable audit records implement shared rolling limits: default 120 attempts/IP and 10/account per 900 seconds across registration/login; refresh consumes the IP limit. Raw email/IP is not recorded in rate-limit scopes. Proxy forwarding is not trusted by application code; operators must configure the ASGI server's trusted proxy addresses explicitly.
- User/profile/audit creation commits atomically. Session changes and audit events commit together. Shared throttling persists independently of failed authentication transactions. SQL parameters are hidden from engine error output.

The choices follow [OWASP password storage guidance](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html), [OWASP signed double-submit CSRF guidance](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html) and [RFC 9700 refresh-token replay guidance](https://www.rfc-editor.org/rfc/rfc9700.html). This is an application session system, not a claim of implementing an OAuth authorization server.

## Roles and administrator provisioning

USER has profile:read, sessions:manage and applications:own. ADMIN retains these and receives only explicitly assigned known scopes: applications:review, analytics:read, reports:read, models:manage, policies:manage, policies:approve, audit:read. Unknown permissions are ignored; USER cannot acquire admin permissions from its JSON list. require_role and require_permission dependencies enforce these rules. Future application ownership must also be checked in queries; a permission name alone does not enforce ownership.

There is no public admin creation/promotion endpoint. A trusted operator may create an administrator using the existing runtime DB credentials:

```powershell
.\.venv\Scripts\python.exe -m scripts.create_admin --email operator@example.com --name "Research Operator" --permission analytics:read --permission applications:review
```

The CLI prompts twice for the password, accepts only known permissions and refuses existing accounts without changing their privileges. No administrator or test user has been seeded into the development database. Protect operator and runtime credentials; direct database access bypasses HTTP authorization.

## Validation evidence and boundary

```powershell
$env:CREDITIQ_TEST_POSTGRES='1'
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
Remove-Item Env:CREDITIQ_TEST_POSTGRES
.\.venv\Scripts\python.exe -m pip check
```

63 tests passed in 71.35 seconds: 34 auth cases plus 29 foundation/database cases. One pre-existing Starlette TestClient/httpx deprecation warning remains. Tests include real restricted-role PostgreSQL requests, duplicate registration, password handling, invalid/expired JWTs, disabled users, CSRF and body limits, logout/session ownership, replay, concurrent rotation, persistent/atomic throttling, live RBAC, cookie flags and fail-closed settings. Existing migration round trips/integrity checks pass. Alembic reports no schema drift, the development database is at 20261003_0002, and pip check reports no broken requirements.

Tests explicitly target creditiq_migration_test; auth fixtures truncate that disposable database between cases, while schema tests use rollback and a migration round trip. Never enable these tests against wanted data. ML tests were not rerun; no ML implementation or artifacts changed.

Milestone 3 is complete. Production readiness remains false: email verification/recovery, MFA, TLS/secret lifecycle, security monitoring, audit/session retention, backup/restore and load/independent security testing remain future work. Immutable rate-limit audit records need a reviewed retention/partitioning design before sustained public traffic. No prediction, application/quote or admin business APIs, frontend or deployment pipeline were implemented. Next milestone: authenticated application drafts, immutable revisions, ownership, server-owned quotes and idempotent submission, before model-serving integration.
