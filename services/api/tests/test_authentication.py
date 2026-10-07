"""Authentication HTTP and race tests against the restricted PostgreSQL app role."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import os
from types import SimpleNamespace
import uuid

from alembic import command
from fastapi import Depends, HTTPException
from fastapi.testclient import TestClient
import jwt
import pytest
from sqlalchemy import create_engine, select, text, update, func
from sqlalchemy.orm import Session

from app.auth.dependencies import require_permission, require_role
from app.auth.rate_limit import check_rate_limit
from app.auth.security import ACCESS_COOKIE, REFRESH_COOKIE, CSRF_COOKIE, digest_token, utcnow
from app.core.config import Settings
from app.db.base import Base
from app.db.models import User, UserProfile, AuthSession, AuditEvent
from app.main import create_app
from app.services import auth as auth_service
from app.services.users import create_user
from scripts.local_db import owner_url, migration_config, grant_application_access

ORIGIN = 'http://testserver'
PASSWORD = 'Correct horse battery staple 47!'
EMAIL = 'borrower@example.com'


@pytest.fixture(scope='module')
def owner_engine():
    if os.environ.get('CREDITIQ_TEST_POSTGRES') != '1':
        pytest.skip('Opt in to the isolated PostgreSQL integration suite')
    engine = create_engine(owner_url('creditiq_migration_test'))
    with engine.begin() as c:
        assert c.scalar(text('SELECT current_database()')) == 'creditiq_migration_test'
        command.upgrade(migration_config(c), 'head')
        grant_application_access(c)
    yield engine
    engine.dispose()


def clean_test_database(engine):
    with engine.begin() as c:
        assert c.scalar(text('SELECT current_database()')) == 'creditiq_migration_test'
        names = ', '.join(f'"{name}"' for name in Base.metadata.tables)
        c.execute(text(f'TRUNCATE {names} CASCADE'))


@pytest.fixture
def api(owner_engine):
    clean_test_database(owner_engine)
    configured = Settings()
    settings = Settings(_env_file=None, app_env='test', lite_enabled=False, jwt_secret='auth-test-secret-' * 4,
        cookie_secure=False, auth_origins=[ORIGIN], auth_ip_limit=1000, auth_account_limit=100,
        pg_host='127.0.0.1', pg_port=55432, pg_database='creditiq_migration_test',
        pg_user='creditiq_app', pg_password=configured.pg_password, pg_sslmode='disable', db_hosting='local')
    app = create_app(settings)

    @app.get('/_test/admin', dependencies=[Depends(require_role('ADMIN'))])
    def admin_probe():
        return {'ok': True}

    @app.get('/_test/analytics', dependencies=[Depends(require_permission('analytics:read'))])
    def permission_probe():
        return {'ok': True}

    with TestClient(app, base_url=ORIGIN, headers={'Origin': ORIGIN}) as client:
        yield client, settings, owner_engine
    clean_test_database(owner_engine)


def mutate(client, method, path, **kwargs):
    token = client.get('/api/v1/auth/csrf').json()['csrf_token']
    return client.request(method, path, headers={'X-CSRF-Token': token}, **kwargs)


def register(client, email=EMAIL, password=PASSWORD):
    return mutate(client, 'POST', '/api/v1/auth/register',
                  json={'email': email, 'password': password, 'full_name': 'Research User'})


def login(client, email=EMAIL, password=PASSWORD):
    return mutate(client, 'POST', '/api/v1/auth/login', json={'email': email, 'password': password})


def signed_in(client):
    assert register(client).status_code == 202
    response = login(client)
    assert response.status_code == 200, response.text
    return response


def restore(client, cookies):
    client.cookies.clear()
    for key, value in cookies.items():
        client.cookies.set(key, value, domain='testserver.local', path='/')


def test_registration_login_and_secret_storage(api):
    client, settings, engine = api
    response = signed_in(client)
    assert response.json()['role'] == 'USER'
    assert 'password' not in response.text and 'access_token' not in response.text
    assert response.headers['cache-control'] == 'no-store'
    assert client.get('/api/v1/me').status_code == 200
    with Session(engine) as db:
        user = db.scalar(select(User))
        assert user.password_hash.startswith('$argon2id$') and user.password_hash != PASSWORD
        assert user.permissions == []
        assert db.scalar(select(UserProfile.full_name)) == 'Research User'
        stored = db.scalar(select(AuthSession.hashed_refresh_token))
        assert stored == digest_token(client.cookies.get(REFRESH_COOKIE))
        assert stored != client.cookies.get(REFRESH_COOKIE)
        assert db.scalar(select(func.count()).select_from(AuditEvent).where(AuditEvent.action=='LOGIN')) == 1
    claims = jwt.decode(client.cookies.get(ACCESS_COOKIE), settings.jwt_secret.get_secret_value(),
                        algorithms=['HS256'], issuer=settings.jwt_issuer, audience=settings.jwt_audience)
    assert claims['token_use'] == 'access'
    assert 'role' not in claims and 'permissions' not in claims
    assert claims['exp'] - claims['iat'] == settings.access_token_minutes * 60


def test_duplicate_registration_casefolded_and_no_enumeration(api):
    client, _, engine = api
    first = register(client, email='Borrower@EXAMPLE.COM')
    second = register(client)
    assert first.status_code == second.status_code == 202 and first.json() == second.json()
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(User)) == 1
    assert login(client, email='BORROWER@example.com').status_code == 200


@pytest.mark.parametrize('extra', [{'role': 'ADMIN'}, {'permissions': ['models:manage']}])
def test_registration_cannot_escalate_privileges(api, extra):
    client, _, engine = api
    response = mutate(client, 'POST', '/api/v1/auth/register', json={
        'email': EMAIL, 'password': PASSWORD, 'full_name': 'User', **extra})
    assert response.status_code == 422 and PASSWORD not in response.text
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(User)) == 0


@pytest.mark.parametrize('password', ['short-secret', 'x' * 129])
def test_password_policy_and_redacted_validation(api, password):
    client, _, _ = api
    response = register(client, password=password)
    assert response.status_code == 422 and password not in response.text


def test_bad_credentials_and_disabled_account_are_generic(api):
    client, _, engine = api
    register(client)
    missing = login(client, email='absent@example.com')
    wrong = login(client, password='wrong password')
    with engine.begin() as c:
        c.execute(update(User).values(account_status='DISABLED'))
    disabled = login(client)
    assert missing.status_code == wrong.status_code == disabled.status_code == 401
    assert missing.json() == wrong.json() == disabled.json()


@pytest.mark.parametrize('failure', ['no_header', 'mismatch', 'untrusted_origin', 'unsigned_cookie', 'no_origin'])
def test_csrf_rejects_mutations(api, failure):
    client, _, _ = api
    token = client.get('/api/v1/auth/csrf').json()['csrf_token']
    headers = {'X-CSRF-Token': token}
    if failure == 'no_header':
        headers = {}
    elif failure == 'mismatch':
        headers['X-CSRF-Token'] = 'wrong'
    elif failure == 'untrusted_origin':
        headers['Origin'] = 'https://attacker.example'
    elif failure == 'unsigned_cookie':
        restore(client, {CSRF_COOKIE: 'unsigned'})
        headers['X-CSRF-Token'] = 'unsigned'
    else:
        client.headers.pop('origin')
    response = client.post('/api/v1/auth/login', headers=headers, json={'email':EMAIL, 'password':PASSWORD})
    assert response.status_code == 403


def test_oversized_body_rejected_before_parsing(api):
    client, _, _ = api
    response = mutate(client, 'POST', '/api/v1/auth/login', content=b'x'*17000)
    assert response.status_code == 413


def test_refresh_rotates_preserves_expiry_and_revokes_old_access(api):
    client, _, engine = api
    signed_in(client)
    original = dict(client.cookies)
    with Session(engine) as db:
        expiry = db.scalar(select(AuthSession.expires_at))
    assert mutate(client, 'POST', '/api/v1/auth/refresh').status_code == 200
    current = dict(client.cookies)
    assert original[REFRESH_COOKIE] != current[REFRESH_COOKIE]
    assert original[ACCESS_COOKIE] != current[ACCESS_COOKIE]
    with Session(engine) as db:
        rows = db.scalars(select(AuthSession).order_by(AuthSession.created_at)).all()
        assert len(rows) == 2 and rows[0].revoked_at is not None and rows[1].revoked_at is None
        assert rows[0].token_family_id == rows[1].token_family_id
        assert rows[1].expires_at == expiry
    restore(client, {**current, ACCESS_COOKIE: original[ACCESS_COOKIE]})
    assert client.get('/api/v1/me').status_code == 401
    restore(client, current)
    assert client.get('/api/v1/me').status_code == 200


def test_refresh_uses_database_clock_when_application_clock_lags(api, monkeypatch):
    client, _, engine = api
    signed_in(client)
    monkeypatch.setattr(auth_service, 'utcnow', lambda: datetime(2000, 1, 1, tzinfo=timezone.utc))
    assert mutate(client, 'POST', '/api/v1/auth/refresh').status_code == 200
    with Session(engine) as db:
        rows = db.scalars(select(AuthSession).order_by(AuthSession.created_at)).all()
        assert len(rows) == 2
        assert rows[0].revoked_at >= rows[0].created_at
        assert rows[1].revoked_at is None


def test_refresh_replay_revokes_current_descendants(api):
    client, _, engine = api
    signed_in(client)
    old = dict(client.cookies)
    assert mutate(client, 'POST', '/api/v1/auth/refresh').status_code == 200
    new = dict(client.cookies)
    restore(client, old)
    assert mutate(client, 'POST', '/api/v1/auth/refresh').status_code == 401
    restore(client, new)
    assert client.get('/api/v1/me').status_code == 401
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(AuthSession).where(AuthSession.revoked_at.is_(None))) == 0
        assert db.scalar(select(func.count()).select_from(AuditEvent).where(AuditEvent.action=='REFRESH_REPLAY')) == 1


def test_concurrent_refresh_only_one_rotation_and_family_revoked(api):
    client, _, engine = api
    signed_in(client)
    raw = client.cookies.get(REFRESH_COOKIE)
    def rotate_once(_):
        with client.app.state.session_factory() as db:
            try:
                auth_service.rotate(db, raw)
                return 'rotated'
            except auth_service.AuthenticationError:
                return 'rejected'
    with ThreadPoolExecutor(max_workers=2) as pool:
        result = list(pool.map(rotate_once, range(2)))
    assert sorted(result) == ['rejected', 'rotated']
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(AuthSession)) == 2
        assert db.scalar(select(func.count()).select_from(AuthSession).where(AuthSession.revoked_at.is_(None))) == 0


def test_logout_invalidates_access_and_refresh(api):
    client, _, _ = api
    signed_in(client)
    saved = dict(client.cookies)
    assert mutate(client, 'POST', '/api/v1/auth/logout').status_code == 204
    assert ACCESS_COOKIE not in client.cookies and REFRESH_COOKIE not in client.cookies
    restore(client, saved)
    assert client.get('/api/v1/me').status_code == 401
    assert mutate(client, 'POST', '/api/v1/auth/refresh').status_code == 401


def test_logout_is_idempotent_and_works_with_expired_access(api):
    client, settings, _ = api
    signed_in(client)
    saved = dict(client.cookies)
    claims = jwt.decode(saved[ACCESS_COOKIE], options={'verify_signature': False})
    claims['exp'] = int(utcnow().timestamp()) - 1
    saved[ACCESS_COOKIE] = jwt.encode(claims, settings.jwt_secret.get_secret_value(), algorithm='HS256')
    restore(client, saved)
    assert mutate(client, 'POST', '/api/v1/auth/logout').status_code == 204
    assert mutate(client, 'POST', '/api/v1/auth/logout').status_code == 204


def test_sessions_ownership_and_logout_all(api):
    client, _, _ = api
    signed_in(client)
    first = dict(client.cookies)
    assert login(client).status_code == 200
    sessions = client.get('/api/v1/auth/sessions').json()
    assert len(sessions) == 2 and sum(row['current'] for row in sessions) == 1
    other = next(row['id'] for row in sessions if not row['current'])
    assert mutate(client, 'DELETE', f'/api/v1/auth/sessions/{other}').status_code == 204
    assert len(client.get('/api/v1/auth/sessions').json()) == 1
    assert mutate(client, 'POST', '/api/v1/auth/logout-all').status_code == 204
    restore(client, first)
    assert client.get('/api/v1/me').status_code == 401


def test_cannot_revoke_another_users_session(api):
    client, _, _ = api
    signed_in(client)
    victim = client.get('/api/v1/auth/sessions').json()[0]['id']
    register(client, email='another@example.com')
    assert login(client, email='another@example.com').status_code == 200
    assert mutate(client, 'DELETE', f'/api/v1/auth/sessions/{victim}').status_code == 404
    assert client.get('/api/v1/me').status_code == 200


@pytest.mark.parametrize('fault', ['signature', 'expired', 'issuer', 'audience', 'purpose', 'missing_sid', 'algorithm'])
def test_invalid_access_tokens_are_rejected(api, fault):
    client, settings, _ = api
    signed_in(client)
    cookies = dict(client.cookies)
    payload = jwt.decode(cookies[ACCESS_COOKIE], options={'verify_signature': False})
    key = settings.jwt_secret.get_secret_value()
    algorithm = 'HS256'
    if fault == 'signature': key = 'invalid-signing-key-' * 4
    if fault == 'expired': payload['exp'] = int(utcnow().timestamp()) - 1
    if fault == 'issuer': payload['iss'] = 'wrong'
    if fault == 'audience': payload['aud'] = 'wrong'
    if fault == 'purpose': payload['token_use'] = 'refresh'
    if fault == 'missing_sid': payload.pop('sid')
    if fault == 'algorithm': algorithm = 'HS384'
    cookies[ACCESS_COOKIE] = jwt.encode(payload, key, algorithm=algorithm)
    restore(client, cookies)
    assert client.get('/api/v1/me').status_code == 401


def test_live_role_permissions_and_disabled_status(api):
    client, _, engine = api
    signed_in(client)
    assert client.get('/_test/admin').status_code == 403
    assert client.get('/_test/analytics').status_code == 403
    with engine.begin() as c:
        c.execute(update(User).values(role='ADMIN', permissions=['analytics:read']))
    assert client.get('/_test/admin').status_code == 200
    assert client.get('/_test/analytics').status_code == 200
    with engine.begin() as c:
        c.execute(update(User).values(permissions=['unknown:permission']))
    assert client.get('/_test/analytics').status_code == 403
    with engine.begin() as c:
        c.execute(update(User).values(role='USER', permissions=['analytics:read']))
    assert client.get('/_test/analytics').status_code == 403
    with engine.begin() as c:
        c.execute(update(User).values(account_status='DISABLED'))
    assert client.get('/api/v1/me').status_code == 401
    assert mutate(client, 'POST', '/api/v1/auth/refresh').status_code == 401


def test_expired_database_session_and_unknown_refresh(api):
    client, _, engine = api
    signed_in(client)
    with engine.begin() as c:
        c.execute(update(AuthSession).values(created_at=utcnow()-timedelta(days=2), expires_at=utcnow()-timedelta(days=1)))
    assert client.get('/api/v1/me').status_code == 401
    assert mutate(client, 'POST', '/api/v1/auth/refresh').status_code == 401
    restore(client, {REFRESH_COOKIE: 'x'*64})
    assert mutate(client, 'POST', '/api/v1/auth/refresh').status_code == 401


def test_account_rate_limit_is_persistent_across_clients(api):
    client, settings, _ = api
    settings.auth_account_limit = 2
    assert login(client).status_code == 401
    assert login(client).status_code == 401
    response = login(client)
    assert response.status_code == 429 and response.headers['retry-after'] == '900'


def test_concurrent_rate_limit_is_atomic(api):
    client, settings, _ = api
    settings.auth_ip_limit = 1
    request = SimpleNamespace(app=client.app, client=SimpleNamespace(host='separate-rate-test'))
    def attempt(_):
        try:
            check_rate_limit(request)
            return 200
        except HTTPException as error:
            return error.status_code
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(attempt, range(4)))
    assert sorted(results) == [200, 429, 429, 429]


def test_trusted_admin_service_and_cookie_security(api):
    client, settings, engine = api
    with client.app.state.session_factory() as db:
        user = create_user(db, email=EMAIL, password=PASSWORD, full_name='Operator',
                           role='ADMIN', permissions=['analytics:read'])
        assert user.role == 'ADMIN'
    response = login(client)
    assert response.status_code == 200 and client.get('/_test/analytics').status_code == 200
    headers = response.headers.get_list('set-cookie')
    assert any('creditiq_access=' in h and 'HttpOnly' in h and 'SameSite=strict' in h for h in headers)
    assert any('creditiq_refresh=' in h and 'HttpOnly' in h for h in headers)
    settings.cookie_secure = True
    settings.auth_origins.append('https://testserver')
    with TestClient(client.app, base_url='https://testserver', headers={'Origin':'https://testserver'}) as secure:
        response = login(secure)
        assert response.status_code == 200
        assert all('Secure' in h and '__Host-' in h and 'Path=/' in h and 'Domain=' not in h
                   for h in response.headers.get_list('set-cookie'))
        assert secure.get('/api/v1/me').status_code == 200


def test_password_hashes_are_salted_and_plaintext_not_echoed(api):
    client, _, engine = api
    register(client)
    register(client, email='second@example.com')
    with Session(engine) as db:
        hashes = db.scalars(select(User.password_hash)).all()
        assert len(hashes) == 2 and hashes[0] != hashes[1]
    assert login(client, password=PASSWORD.lower()).status_code == 401


def test_missing_secret_and_insecure_production_configuration_fail_closed():
    with pytest.raises(ValueError):
        create_app(Settings(_env_file=None, jwt_secret=None))
    with pytest.raises(ValueError):
        create_app(Settings(_env_file=None, app_env='production', jwt_secret='x'*64, cookie_secure=False))
    with pytest.raises(ValueError):
        create_app(Settings(_env_file=None, jwt_secret='x'*64, auth_origins=['*']))
