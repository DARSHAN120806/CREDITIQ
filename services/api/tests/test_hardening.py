"""Fail-closed configuration, startup, readiness and transport/logging security."""
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.core.config import Settings
from app.main import create_app


def configured(**overrides):
    values = dict(_env_file=None, app_env='test', lite_enabled=False,
                  jwt_secret='Q7n4hZwXk32Sy86tJo9lRdVcE5uA1iBbFpM0GsHx', db_hosting='local', cookie_secure=True,
                  api_origin='https://api.example.com', frontend_origin='https://app.example.com',
                  trusted_proxy_ips='127.0.0.1',
                  pg_host='test.invalid', pg_port=5432, pg_database='test',
                  pg_user='test', pg_password='test-password')
    values.update(overrides)
    return Settings(**values)


@pytest.mark.parametrize('field', ['pg_host', 'pg_port', 'pg_database', 'pg_user', 'pg_password'])
def test_each_required_database_setting_fails_closed(field):
    with pytest.raises(ValueError, match='Required database settings'):
        create_app(configured(**{field: None}))


def test_no_database_defaults(monkeypatch):
    for name in ("HOST", "PORT", "DATABASE", "USER", "PASSWORD"):
        monkeypatch.delenv("CREDITIQ_PG_" + name, raising=False)
    with pytest.raises(ValueError, match='Required database settings'):
        _ = Settings(_env_file=None).database_url


@pytest.mark.parametrize('hosting,host,ssl,user', [
    ('local', '127.0.0.1', 'verify-full', 'runtime'),
    ('supabase', 'localhost', 'verify-full', 'runtime'),
    ('supabase', 'test.supabase.com', 'require', 'runtime'),
    ('supabase', 'test.supabase.com', 'verify-full', 'postgres.project'),
])
def test_production_rejects_local_insecure_or_privileged_config(hosting, host, ssl, user):
    with pytest.raises(ValueError):
        create_app(configured(app_env='production', db_hosting=hosting, pg_host=host,
                             pg_sslmode=ssl, pg_user=user, auth_origins=['https://app.example.com']))


def test_startup_failure_is_sanitized_and_disposes_engine(caplog):
    engine = MagicMock()
    engine.connect.side_effect = OperationalError('secret SQL', {'password': 'secret value'}, Exception('private-host'))
    with patch('app.main.build_engine', return_value=engine), pytest.raises(RuntimeError, match='startup validation failed'):
        with TestClient(create_app(configured())):
            pass
    engine.dispose.assert_called_once()
    assert 'database_startup_failed' in caplog.text
    assert 'secret value' not in caplog.text and 'private-host' not in caplog.text


def test_ready_queries_database_and_returns_sanitized_503():
    engine = MagicMock()
    with patch('app.main.build_engine', return_value=engine), TestClient(create_app(configured())) as client:
        engine.connect.reset_mock()
        assert client.get('/health/ready').json() == {'status': 'ready'}
        engine.connect.assert_called_once()
        engine.connect.side_effect = OperationalError('private SQL', {}, Exception('secret'))
        response = client.get('/api/v1/health/ready')
        assert response.status_code == 503 and response.json() == {'status': 'unavailable'}
        assert response.headers['cache-control'] == 'no-store'
        assert client.get('/health/live').status_code == 200


def test_https_hsts_cors_and_unexpected_error_redaction(caplog):
    app = create_app(configured(app_env='production', db_hosting='supabase',
                     pg_host='test.supabase.com', pg_sslmode='verify-full',
                     pg_user='runtime.project', auth_origins=['https://app.example.com']))

    @app.get('/_test/error')
    def private_error():
        raise RuntimeError('secret password and SQL')

    engine = MagicMock()
    engine.connect.return_value.__enter__.return_value.execute.return_value.scalar_one.return_value = False
    with patch('app.main.build_engine', return_value=engine), TestClient(app, base_url='https://app.example.com') as client:
        assert client.get('http://app.example.com/health/live').status_code == 200
        assert client.get('http://app.example.com/api/v1/me').status_code == 400
        response = client.get('/health/live', headers={'Origin': 'https://app.example.com'})
        assert response.headers['strict-transport-security'] == 'max-age=31536000'
        assert response.headers['access-control-allow-origin'] == 'https://app.example.com'
        assert 'access-control-allow-origin' not in client.get('/health/live', headers={'Origin': 'https://evil.example'}).headers
        assert client.get('/_test/error').status_code == 500
        assert 'secret password' not in caplog.text


def test_migrations_reject_transaction_pooler():
    for host in ('region.pooler.supabase.com', 'db.project.supabase.co'):
        with pytest.raises(ValueError, match='direct or session'):
            _ = configured(db_hosting='supabase', migration_database_url=
                f'postgresql+psycopg://operator:test@{host}:6543/postgres?sslmode=verify-full').migration_url


def test_production_startup_rejects_administrative_role():
    engine = MagicMock()
    engine.connect.return_value.__enter__.return_value.execute.return_value.scalar_one.return_value = True
    settings = configured(app_env='production', db_hosting='supabase', pg_host='db.test.supabase.co',
                          pg_sslmode='verify-full', pg_user='runtime', auth_origins=['https://app.example.com'])
    with patch('app.main.build_engine', return_value=engine), pytest.raises(RuntimeError, match='administrative privileges'):
        with TestClient(create_app(settings)):
            pass
    engine.dispose.assert_called_once()
