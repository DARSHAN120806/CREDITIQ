from io import StringIO

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from pydantic import ValidationError
from unittest.mock import MagicMock, patch

from app.core.config import API_ROOT, Settings
from app.db.base import Base
from app.db import models
from app.main import create_app


def test_liveness_without_database_and_without_domain_routes():
    settings = Settings(_env_file=None, app_env='test', lite_enabled=False,
                        jwt_secret='foundation-test-secret-' * 3, db_hosting='local',
                        pg_host='test.invalid', pg_port=5432, pg_database='test',
                        pg_user='test', pg_password='test-password')
    with patch('app.main.build_engine', return_value=MagicMock()) as build, TestClient(create_app(settings)) as client:
        build.return_value.connect.reset_mock()  # Startup checks DB; liveness itself must not.
        assert client.get("/api/v1/health/live").json() == {"status": "ok"}
        assert client.get('/health/live').json() == {'status': 'ok'}
        build.return_value.connect.assert_not_called()
        paths = set(client.get("/openapi.json").json()["paths"])
        assert '/api/v1/auth/login' in paths and '/api/v1/me' in paths
        assert '/api/v1/applications' in paths and '/api/v1/admin/statistics' in paths
        assert len(Base.metadata.tables) == 28


def test_environment_settings_and_password_handling(monkeypatch):
    monkeypatch.setenv("CREDITIQ_PG_PORT", "5433")
    monkeypatch.setenv("CREDITIQ_PG_PASSWORD", "a@b:%/secret")
    settings = Settings(_env_file=None, db_hosting='local', pg_host='test.invalid',
                        pg_database='test', pg_user='test')
    assert settings.database_url.port == 5433
    assert settings.database_url.password == "a@b:%/secret"
    assert "a@b:%/secret" not in repr(settings)
    assert "a@b:%/secret" not in str(settings.database_url)
    with pytest.raises(ValidationError):
        Settings(_env_file=None, pg_port=0)
    with pytest.raises(ValidationError):
        Settings(_env_file=None, db_pool_size=0)


def test_alembic_offline_schema_without_connection(monkeypatch):
    monkeypatch.setenv('CREDITIQ_MIGRATION_DATABASE_URL',
                      'postgresql+psycopg://operator:test-password@test.supabase.com:5432/test?sslmode=verify-full')
    output = StringIO()
    config = Config(str(API_ROOT / "alembic.ini"), output_buffer=output)
    command.upgrade(config, "head", sql=True)
    assert "CREATE TABLE users" in output.getvalue()
    assert 'fk_application_current_decision' in output.getvalue()


def test_research_configuration_cannot_enable_release(monkeypatch):
    monkeypatch.setenv('CREDITIQ_RELEASE_READY', 'false')
    assert Settings(_env_file=None).release_ready is False
    monkeypatch.setenv('CREDITIQ_RELEASE_READY', 'true')
    with pytest.raises(ValidationError):
        Settings(_env_file=None)
    with pytest.raises(ValidationError):
        Settings(_env_file=None, release_ready=False, mode='LIVE')

