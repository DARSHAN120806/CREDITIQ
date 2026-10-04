# CreditIQ authentication validation checkpoint

Checkpoint: 3 October 2026. Documentation-only handoff after the explicit stop instruction. **Milestone 3 is COMPLETE for the requested authentication/authorization scope.** Milestones 1 and 2 remain intact. No Milestone 4 work has started. Backend mode=RESEARCH_ONLY, release_ready=false; no production readiness claim.

## Files created and modified during Milestone 3

Created under services/api:

- app/auth/__init__.py, security.py, dependencies.py, rate_limit.py, middleware.py.
- app/schemas/auth.py, app/services/users.py, app/services/auth.py, app/routers/auth.py.
- migrations/versions/20261003_0002_auth_indexes.py, scripts/create_admin.py.
- tests/test_authentication.py and AUTHENTICATION.md.

Modified under services/api:

- app/core/config.py, app/main.py, app/db/session.py, app/db/models/schema.py (indexes only).
- scripts/local_db.py, tests/test_foundation.py, tests/test_database.py.
- requirements.txt, requirements-lock.txt, .env.example, README.md, DATABASE_VALIDATION.md, schema.sql.
- Ignored .env gained a random signing secret and local HTTP cookie configuration; no credentials are in tracked files.

Modified root tracking: PROJECT_PROGRESS.md, BACKEND_TODO.md, BACKEND_ARCHITECTURE.md, PROJECT_STATUS_REPORT.md and CHANGELOG.md.

This final documentation checkpoint additionally creates root AUTH_VALIDATION.md and updates PROJECT_PROGRESS.md, BACKEND_TODO.md, BACKEND_ARCHITECTURE.md and PROJECT_STATUS_REPORT.md. No implementation files changed after the stop instruction. The file inventory is based on this session's operations; this workspace has no Git repository for a Git diff comparison.

## Database changes and applied migrations

- Existing revision 20261003_0001_initial_research_schema.py is preserved.
- Added and applied revision 20261003_0002_auth_indexes.py, with down_revision=20261003_0001.
- Three indexes only: ix_auth_sessions_user_family (user_id, token_family_id), ix_auth_sessions_active_expiry (user_id, expires_at) WHERE revoked_at IS NULL, and ix_audit_auth_rate (action, entity_id, created_at).
- All 24 existing tables retained. Authentication reuses users, user_profiles, auth_sessions and audit_events. No table recreation or altered ML schema.
- Development creditiq is at 20261003_0002; disposable creditiq_migration_test completed migration round-trip tests through head. Development Alembic check: no new upgrade operations detected.
- Regenerated services/api/schema.sql through both revisions. Runtime credentials remain restricted; local_db shares the existing runtime grants with test setup. Development users count verified zero.
- PostgreSQL 18.6 is reachable through the existing isolated 127.0.0.1:55432 cluster using creditiq_app. Installed Windows PostgreSQL instances remain untouched.

## Authentication architecture and endpoint contracts

FastAPI routes use Pydantic request/response contracts, synchronous SQLAlchemy sessions and explicit service transactions. app/auth contains password/JWT/CSRF primitives, request safety middleware, reusable live database authorization dependencies and shared PostgreSQL rate limits. app/services/users.py manages atomic user/profile creation; app/services/auth.py manages session rotation/revocation. No frontend or model serving is involved.

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


## Audit logging changes

Existing immutable audit_events stores USER_CREATED, LOGIN, REFRESH_ROTATED, REFRESH_REPLAY, LOGOUT, SESSION_REVOKED and ALL_SESSIONS_REVOKED. Entries carry actor/entity identity, generated request identifier and redacted metadata; no passwords or raw access/refresh credentials are recorded. Session mutation and its audit event commit together; replay revocation commits before returning 401.

AUTH_RATE entries persist separately from authentication transactions, including failed attempts. Scope identities use purpose-separated HMAC-derived UUIDs rather than raw email/IP. Advisory transaction locks make the rolling counter atomic across API workers. Audit records are not automatically deleted; retention/partitioning remains an operational follow-up. Failed credential attempts produce throttle records rather than a separate detailed failed-login event taxonomy.

## Tests executed and results

All commands ran in services/api with the isolated backend .venv and real project-local PostgreSQL.

1. Foundation check: 4 passed, one pre-existing TestClient warning.
2. Initial authentication suite: 29 passed and 5 failed. Failures were traced to test cookie path/domain handling and test-only RBAC routes outside the previous cookie path. Cookie handling was corrected, Secure __Host- cookie support standardized Path=/, and the complete authentication suite was rerun.
3. Final authentication-only suite: **34 passed, 1 warning, 59.08 seconds**.
4. Final full backend regression suite: **63 passed, 1 warning, 71.35 seconds**. This includes those 34 auth tests plus 29 foundation/database cases; these counts are not additive across runs.
5. pip check: no broken requirements.
6. Development Alembic check: no new upgrade operations detected; head 20261003_0002.
7. Restricted runtime connectivity: 24 visible application tables, RESEARCH_ONLY, release_ready=false. Development users count zero.
8. Read-only ML integrity verification: all nine registered real Lite artifact checksums and 14 ML package source hashes match metadata; latest.json identifies run 20261002T140817Z-045430a7; research release flags unchanged. No artifact loading, retraining or ML tests performed in this milestone.

Coverage includes registration/duplicate normalization, privilege injection rejection, password bounds/salting, validation redaction, generic credential errors, inactive accounts, malformed/expired JWTs, CSRF failures, body limit, refresh rotation/absolute expiry, replay revocation, concurrent rotation, logout with expired access, own-session boundaries, logout-all, live role/scope changes, shared and concurrent rate limits, Secure cookie properties and fail-closed settings. Foundation/database tests cover migrations, integrity constraints, immutability, rollback and restricted privileges.

Exact full-suite command (from services/api, PowerShell):

```powershell
$env:CREDITIQ_TEST_POSTGRES='1'
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
Remove-Item Env:CREDITIQ_TEST_POSTGRES
```

Integration tests are opt-in and confined to creditiq_migration_test. Auth fixtures truncate that disposable database; existing database tests use transaction rollbacks and a controlled migration round trip. Never point these tests at wanted data. No tests were rerun for this documentation-only checkpoint.

## Known limitations and remaining blockers

- No remaining blocker for the requested Milestone 3 scope. The sole test warning is the existing Starlette TestClient/httpx deprecation, not a failing check.
- Production remains blocked by deployment TLS/secret lifecycle, recovery/email verification, MFA, operational monitoring, retention, backup/restore, load testing and independent security review. These are not claims of implemented controls.
- Email registration creates an ACTIVE account without proving mailbox ownership; it is suitable only within the documented research boundary pending a verified-account flow.
- Cookie-only authentication requires explicit Origin/CSRF handling and same-site hosting. Refresh operations must be serialized across browser tabs; replay detection also treats duplicate refresh retries as reuse and revokes the family.
- JWT signing-key rotation currently invalidates existing tokens; no multi-key overlap protocol is implemented. Configured secret length validation cannot itself prove randomness.
- Account throttling can temporarily block legitimate login after repeated attempts; tune thresholds using measured traffic. Proxy trust and denial-of-service/load behavior require deployment validation.
- Runtime SQL credentials are trusted infrastructure; HTTP RBAC does not protect against direct database access. Future lending/business transactions need their own ownership and transaction-time authorization enforcement.
- Recovery, password-change/account-management flows and detailed failed-login monitoring are later product/security work. Admin provisioning is a trusted CLI, not an admin management API.
- The development repository has no Git metadata. Secrets remain in ignored local .env/.postgres files; preserve them locally without copying into documentation.
- Existing ML acceptance gaps (real Lite SHAP, Full source/training/segmentation and production gates) are unchanged. No prediction APIs, admin business workflows, frontend or deployment were implemented.

## Recommended Milestone 4 scope

Implement authenticated application drafts, immutable application revisions, server-owned quote validation, owner-scoped read/update operations, consent handling required by the existing schema/design, and idempotent submission with transactional audit/history tests. Reuse the schema and the new authentication dependencies. Validate JSON contracts, ownership, stale-version/concurrent mutation handling and request replay. Do not begin model loading/scoring, admin business APIs, frontend or deployment in that milestone unless explicitly authorized. Preserve RESEARCH_ONLY and release_ready=false.

Recommended next prompt:

> Read PROJECT_PROGRESS.md, BACKEND_TODO.md, BACKEND_ARCHITECTURE.md, PROJECT_STATUS_REPORT.md, AUTH_VALIDATION.md and CREDITIQ_DESIGN.md. Milestones 1–3 are complete; do not recreate them. Start Milestone 4 only: authenticated application drafts/revisions, ownership enforcement, server-owned quotes, required consent handling and idempotent submission with transaction/audit tests. First reconcile the exact scope with the existing design and schema and show a file-level implementation plan. Reuse authentication and existing tables, add reviewed migrations only if necessary, keep RESEARCH_ONLY and release_ready=false, and do not touch ML artifacts, model serving, admin business APIs, frontend or deployment. Update tracking after each completed step and stop after Milestone 4 validation.
