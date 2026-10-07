"""Supabase candidate smoke tests; all fixture writes roll back in one outer transaction."""
import json
import secrets
import sys
import uuid

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.core.config import API_ROOT, Settings
from app.db.session import build_engine
from app.main import create_app
from app.services.users import create_user
from scripts.secure_supabase_access import fingerprints


def main():
    private = API_ROOT / '.postgres'
    settings = Settings(_env_file=private / 'runtime-candidate.env', app_env='staging',
                        cookie_secure=True, auth_origins=['https://testserver'],
                        api_origin='https://api.testserver', frontend_origin='https://testserver',
                        trusted_proxy_ips='127.0.0.1')
    operator = Settings(_env_file=private / 'runtime-role-previous.env')
    owner = create_engine(operator.database_url, hide_parameters=True)
    engine = build_engine(settings)
    checks = []
    with owner.connect() as c:
        before = fingerprints(c)
    try:
        with engine.connect() as connection:
            outer = connection.begin()
            try:
                assert connection.scalar(text('SELECT current_user')) == 'creditiq_runtime'
                flags = connection.execute(text('SELECT rolsuper,rolcreatedb,rolcreaterole,rolreplication,rolbypassrls FROM pg_roles WHERE rolname=current_user')).one()
                assert not any(flags)
                assert not connection.scalar(text('SELECT count(*) FROM pg_auth_members WHERE member=(SELECT oid FROM pg_roles WHERE rolname=current_user)'))
                checks.append('restricted identity and zero memberships')
                probes = [
                    'CREATE TABLE public.runtime_forbidden_probe (id int)',
                    'ALTER TABLE public.users DISABLE ROW LEVEL SECURITY',
                    'TRUNCATE public.users',
                    'DELETE FROM public.users WHERE false',
                    "UPDATE public.users SET role='ADMIN' WHERE false",
                    'UPDATE public.predictions SET calibrated_pd=0 WHERE false',
                    'SELECT * FROM public.alembic_version',
                    'SELECT * FROM public.outbox_events',
                    'SET ROLE postgres', 'SET ROLE service_role',
                ]
                for statement in probes:
                    with connection.begin_nested() as savepoint:
                        try:
                            connection.execute(text(statement))
                        except Exception as exc:
                            assert getattr(exc.orig, 'sqlstate', None) == '42501'
                            savepoint.rollback()
                        else:
                            raise AssertionError('Forbidden privilege succeeded')
                checks.append('10 forbidden SQL operations denied')
                app = create_app(settings)
                with TestClient(app, base_url='https://testserver', headers={'Origin': 'https://testserver'}) as client:
                    assert client.get('/health/live').status_code == 200
                    assert client.get('/health/ready').status_code == 200
                    original_factory = app.state.session_factory
                    factory = sessionmaker(bind=connection, autoflush=False, expire_on_commit=False,
                                           join_transaction_mode='create_savepoint')
                    app.state.session_factory = factory

                    def mutate(method, path, expected, **kwargs):
                        csrf = client.get('/api/v1/auth/csrf').json()['csrf_token']
                        headers = kwargs.pop('headers', {})
                        response = client.request(method, path, headers={'X-CSRF-Token': csrf, **headers}, **kwargs)
                        assert response.status_code == expected, (path, response.status_code)
                        checks.append(method + ' ' + path + ' ' + str(expected))
                        return response

                    def get(path, expected=200):
                        response = client.get(path)
                        assert response.status_code == expected, (path, response.status_code)
                        checks.append('GET ' + path + ' ' + str(expected))
                        return response

                    password = secrets.token_urlsafe(32)
                    email = f'role-validation-{uuid.uuid4()}@example.com'
                    credentials = {'email': email, 'password': password}
                    get('/api/v1/applications', 401)
                    mutate('POST', '/api/v1/auth/register', 202, json={**credentials, 'full_name': 'Rollback validation'})
                    mutate('POST', '/api/v1/auth/login', 200, json=credentials)
                    get('/api/v1/me')
                    get('/api/v1/auth/sessions')
                    mutate('POST', '/api/v1/auth/refresh', 200)
                    # Reuse existing valid fixtures, not a parallel business implementation.
                    sys.path.insert(0, str(API_ROOT / 'tests'))
                    from test_applications import BODY
                    from test_installment_metrics import history
                    from test_borrowing_planner import body
                    key = str(uuid.uuid4())
                    result = mutate('POST', '/api/v1/applications', 201, json=BODY, headers={'Idempotency-Key': key}).json()
                    identity = result['id']
                    replay = mutate('POST', '/api/v1/applications', 201, json=BODY, headers={'Idempotency-Key': key}).json()
                    assert replay['id'] == identity
                    for path in ('/applications', '/applications/'+identity, '/applications/'+identity+'/result', '/applications/'+identity+'/history'):
                        get('/api/v1'+path)
                    analysis = mutate('POST', '/api/v1/installment-history/imports', 201, json=history(), headers={'Idempotency-Key': str(uuid.uuid4())}).json()
                    for path in ('/installment-analyses', '/installment-analyses/'+analysis['id'], '/installment-analyses/'+analysis['id']+'/timeline'):
                        get('/api/v1'+path)
                    mutate('POST', '/api/v1/planner/plan', 200, json=body(application_id=identity).model_dump(mode='json'))
                    get('/api/v1/admin/users', 403)
                    session = get('/api/v1/auth/sessions').json()[0]['id']
                    mutate('DELETE', '/api/v1/auth/sessions/'+session, 204)
                    get('/api/v1/me', 401)
                    mutate('POST', '/api/v1/auth/login', 200, json=credentials)
                    mutate('POST', '/api/v1/auth/logout', 204)
                    get('/api/v1/me', 401)
                    # A second user must not see the first user's records.
                    other = {**credentials, 'email': f'other-{uuid.uuid4()}@example.com'}
                    mutate('POST', '/api/v1/auth/register', 202, json={**other, 'full_name': 'Other rollback user'})
                    mutate('POST', '/api/v1/auth/login', 200, json=other)
                    get('/api/v1/applications/'+identity, 404)
                    get('/api/v1/installment-analyses/'+analysis['id'], 404)
                    mutate('POST', '/api/v1/auth/logout', 204)
                    admin_email = f'admin-{uuid.uuid4()}@example.com'
                    with factory() as db:
                        create_user(db, email=admin_email, password=password, full_name='Rollback admin', role='ADMIN')
                    mutate('POST', '/api/v1/auth/login', 200, json={'email': admin_email, 'password': password})
                    for path in ('users', 'applications', 'applications/'+identity, 'statistics', 'model-research', 'customer-segmentation', 'installment-analyses', 'installment-statistics'):
                        get('/api/v1/admin/'+path)
                    mutate('POST', '/api/v1/applications', 403, json=BODY, headers={'Idempotency-Key': str(uuid.uuid4())})
                    mutate('POST', '/api/v1/auth/logout', 204)
                    app.state.session_factory = original_factory
            finally:
                outer.rollback()
        with owner.connect() as c:
            after = fingerprints(c)
        assert before == after, 'Supabase records changed during rollback-only validation'
        output = {'passed': len(checks), 'checks': checks, 'data_unchanged': True,
                  'before': before, 'after': after, 'production_startup_role_gate': 'passed'}
        (private / 'runtime-validation.json').write_text(json.dumps(output, indent=2), encoding='utf-8')
        print(json.dumps({'passed': len(checks), 'data_unchanged': True}))
    finally:
        engine.dispose()
        owner.dispose()


if __name__ == '__main__':
    main()
