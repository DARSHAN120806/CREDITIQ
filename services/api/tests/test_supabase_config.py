"""Connection configuration checks: no external credentials or connections."""
from unittest.mock import patch

import pytest
from sqlalchemy import URL

from app.core.config import Settings
from app.db.session import build_engine


def configured(**kwargs):
    values = dict(_env_file=None, db_hosting="local", pg_host="test.invalid", pg_port=5432,
                  pg_database="test", pg_user="test", pg_password="test-password")
    values.update(kwargs)
    return Settings(**values)


def test_explicit_local_config_and_special_characters_are_preserved():
    settings = configured( pg_password="test@:/%secret")
    assert settings.migration_url == settings.database_url
    assert settings.database_url.password == "test@:/%secret"
    assert "test@:/%secret" not in repr(settings)


@pytest.mark.parametrize("mode", ["direct", "session", "transaction"])
def test_engine_prepared_statements_configuration(mode):
    settings = configured( pg_connection_mode=mode)
    with patch("app.db.session.create_engine") as create, patch('app.db.session.event.listen') as listen:
        build_engine(settings)
    args = create.call_args.kwargs
    assert args["hide_parameters"] is True
    assert args["connect_args"]["connect_timeout"] == 5
    from unittest.mock import MagicMock
    connection = MagicMock()
    listen.call_args.args[2](connection)
    assert connection.exec_driver_sql.call_args_list[0].args == ("SET LOCAL statement_timeout = '15000ms'",)
    assert connection.exec_driver_sql.call_args_list[1].args == ("SET LOCAL lock_timeout = '5000ms'",)
    assert args["pool_recycle"] == 300
    assert (args["connect_args"].get("prepare_threshold", "default") is None) == (mode == "transaction")


@pytest.mark.parametrize("sslmode", ["disable", "allow", "prefer"])
def test_supabase_rejects_unencrypted_runtime(sslmode):
    with pytest.raises(ValueError, match="require TLS"):
        configured( db_hosting="supabase", pg_host="test.supabase.com", pg_sslmode=sslmode).database_url


def test_supabase_requires_separate_operator_connection():
    settings = configured( db_hosting="supabase", pg_host="test.supabase.com", pg_sslmode="require")
    assert settings.database_url.query["sslmode"] == "require"
    with pytest.raises(ValueError, match="MIGRATION_DATABASE_URL"):
        _ = settings.migration_url


def test_migration_url_and_ca_are_independent_from_runtime(tmp_path):
    ca = tmp_path / "ca.pem"
    ca.write_text("test certificate")
    url = URL.create("postgresql+psycopg", username="operator", password="test@:/%secret",
                     host="migration.supabase.com", database="test",
                     query={"sslmode": "verify-full", "sslrootcert": "C:/cert/ca.pem"})
    settings = configured( db_hosting="supabase", pg_host="runtime.supabase.com",
                        pg_sslmode="verify-full", pg_sslrootcert=str(ca),
                        migration_database_url=url.render_as_string(hide_password=False))
    assert settings.migration_url == url
    assert settings.database_url.host == "runtime.supabase.com"
    assert settings.database_url.query["sslrootcert"] == str(ca)
    assert "test@:/%secret" not in repr(settings)


@pytest.mark.parametrize("value", ["bad-secret-url", "sqlite:///test.db",
                                  "postgresql+psycopg://operator@migration.supabase.com/test"])
def test_invalid_migration_urls_fail_without_echoing_input(value):
    with pytest.raises(ValueError) as error:
        _ = configured( db_hosting="supabase", migration_database_url=value).migration_url
    assert value not in str(error.value)
