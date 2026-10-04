from io import StringIO

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import event

from app.core.config import API_ROOT, Settings
from app.db.base import Base
from app.db import models
from app.main import create_app


def test_liveness_without_database_and_without_domain_routes():
    with TestClient(create_app(Settings(_env_file=None, app_env="test", lite_enabled=False, jwt_secret='foundation-test-secret-' * 3))) as client:
        engine = client.app.state.session_factory.kw["bind"]

        @event.listens_for(engine, "do_connect")
        def no_database(*args, **kwargs):
            pytest.fail("Liveness must not connect to PostgreSQL")

        assert client.get("/api/v1/health/live").json() == {"status": "ok"}
        paths = set(client.get("/openapi.json").json()["paths"])
        assert '/api/v1/auth/login' in paths and '/api/v1/me' in paths
        assert '/api/v1/applications' in paths and '/api/v1/admin/statistics' in paths
        assert len(Base.metadata.tables) == 28


def test_environment_settings_and_password_handling(monkeypatch):
    monkeypatch.setenv("CREDITIQ_PG_PORT", "5433")
    monkeypatch.setenv("CREDITIQ_PG_PASSWORD", "a@b:%/secret")
    settings = Settings(_env_file=None)
    assert settings.database_url.port == 5433
    assert settings.database_url.password == "a@b:%/secret"
    assert "a@b:%/secret" not in repr(settings)
    assert "a@b:%/secret" not in str(settings.database_url)
    with pytest.raises(ValidationError):
        Settings(_env_file=None, pg_port=0)
    with pytest.raises(ValidationError):
        Settings(_env_file=None, db_pool_size=0)


def test_alembic_offline_schema_without_connection():
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

