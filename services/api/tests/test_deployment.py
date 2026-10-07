import json
import pytest
from app.core.startup_environment_validator import validate_startup_environment
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
