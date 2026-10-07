import json
import runpy
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from app.core.startup_environment_validator import validate_startup_environment
from app.main import create_app
from test_hardening import configured


def deployment(**changes):
    values = dict(app_env='production', db_hosting='supabase', pg_host='db.test.supabase.co',
                  pg_sslmode='verify-full', pg_user='creditiq_runtime.project',
                  auth_origins=['https://app.example.com'])
    values.update(changes)
    return configured(**values)


@pytest.mark.parametrize('change', [
    {'auth_origins': ['http://app.example.com']}, {'cookie_secure': False},
    {'pg_sslmode': 'require'}, {'pg_host': '127.0.0.1'}, {'pg_user': 'postgres.project'},
    {'pg_password': None}, {'jwt_secret': 'x'*64}, {'jwt_secret': 'abcdEFG123456789'*4},
    {'api_origin': None}, {'frontend_origin': None}, {'trusted_proxy_ips': None},
    {'trusted_proxy_ips': '*'}, {'trusted_proxy_ips': '0.0.0.0/0'},
    {'trusted_proxy_ips': '::/0'}, {'api_origin': 'http://api.example.com'},
    {'api_origin': 'https://secret:password@api.example.com'},
    {'migration_database_url': 'postgresql+psycopg://operator:secret@db.test.supabase.co/postgres'},
])
def test_deployment_fails_closed(change):
    with pytest.raises(ValueError):
        validate_startup_environment(deployment(**change))


def test_safe_startup_summary_has_no_credentials():
    settings = deployment()
    summary = validate_startup_environment(settings)
    encoded = json.dumps(summary)
    assert settings.pg_password.get_secret_value() not in encoded
    assert settings.jwt_secret.get_secret_value() not in encoded
    assert summary['runtime_role'] == 'creditiq_runtime'
    assert summary['ssl_mode'] == 'verify-full'
    assert summary['cookie_secure'] is True


def test_render_web_uses_edge_https_without_trusting_proxy_headers(monkeypatch):
    monkeypatch.setenv('RENDER', 'true')
    monkeypatch.setenv('RENDER_SERVICE_TYPE', 'web')
    settings = deployment(trusted_proxy_ips=None, lite_enabled=False)
    assert validate_startup_environment(settings)['https_enforcement'] == 'render_edge'

    with patch('app.main.build_engine') as build_engine:
        connection = build_engine.return_value.connect.return_value.__enter__.return_value
        connection.execute.return_value.scalar_one.return_value = False
        with TestClient(create_app(settings), base_url='http://api.example.com') as client:
            response = client.get('/api/v1/me', headers={'X-Forwarded-Proto': 'https'})
            assert response.status_code == 401  # Auth still runs behind Render's HTTP hop.
            assert response.headers['strict-transport-security'] == 'max-age=31536000'

    with patch('app.core.config.Settings', return_value=settings), patch('uvicorn.run') as run:
        runpy.run_module('scripts.start_server', run_name='__main__')
    assert run.call_args.kwargs['proxy_headers'] is False
    assert run.call_args.kwargs['forwarded_allow_ips'] == '127.0.0.1'


def test_render_mode_rejects_proxy_trust_and_requires_web_service(monkeypatch):
    monkeypatch.setenv('RENDER', 'true')
    monkeypatch.setenv('RENDER_SERVICE_TYPE', 'web')
    with pytest.raises(ValueError, match='proxy headers are disabled'):
        validate_startup_environment(deployment(trusted_proxy_ips='*'))
    monkeypatch.setenv('RENDER_SERVICE_TYPE', 'worker')
    with pytest.raises(ValueError, match='TRUSTED_PROXY_IPS is required'):
        validate_startup_environment(deployment(trusted_proxy_ips=None))
