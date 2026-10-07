"""Typed environment settings shared by FastAPI and Alembic."""
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError

API_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="CREDITIQ_", env_file=API_ROOT / ".env",
        env_file_encoding="utf-8", extra="ignore",
    )

    app_env: Literal["development", "test", "staging", "production"] = "development"
    mode: Literal["RESEARCH_ONLY"] = "RESEARCH_ONLY"
    release_ready: Literal[False] = False
    pg_host: str | None = None
    pg_port: int | None = Field(default=None, ge=1, le=65535)
    pg_database: str | None = None
    pg_user: str | None = None
    pg_password: SecretStr | None = None
    pg_sslmode: Literal["disable", "allow", "prefer", "require", "verify-ca", "verify-full"] = "prefer"
    pg_sslrootcert: str | None = None
    db_hosting: Literal["local", "supabase"] = "supabase"
    pg_connection_mode: Literal["direct", "session", "transaction"] = "direct"
    # Operator-only credentials. Never required by the running API.
    migration_database_url: SecretStr | None = None
    db_pool_size: int = Field(default=5, ge=1)
    db_max_overflow: int = Field(default=5, ge=0)
    db_connect_timeout: int = Field(default=5, ge=1, le=30)
    db_pool_timeout: int = Field(default=30, ge=1, le=60)
    db_pool_recycle: int = Field(default=300, ge=30)
    db_statement_timeout_ms: int = Field(default=15000, ge=1000, le=120000)
    db_lock_timeout_ms: int = Field(default=5000, ge=100, le=30000)
    lite_enabled: bool = True
    api_origin: str | None = None
    frontend_origin: str | None = None
    trusted_proxy_ips: str | None = None
    jwt_secret: SecretStr | None = None
    jwt_issuer: str = 'creditiq-api'
    jwt_audience: str = 'creditiq-web'
    access_token_minutes: int = Field(default=15, ge=1, le=30)
    refresh_token_days: int = Field(default=30, ge=1, le=30)
    cookie_secure: bool = True
    auth_origins: list[str] = ['http://127.0.0.1:8000', 'http://localhost:8000', 'http://127.0.0.1:3000', 'http://localhost:3000']
    auth_ip_limit: int = Field(default=120, ge=1, le=1000)
    auth_account_limit: int = Field(default=10, ge=1, le=1000)
    auth_window_seconds: int = Field(default=900, ge=60, le=3600)

    def validate_auth(self) -> None:
        from urllib.parse import urlsplit
        if self.jwt_secret is None or len(self.jwt_secret.get_secret_value().encode()) < 32:
            raise ValueError('CREDITIQ_JWT_SECRET must contain at least 32 random bytes')
        if not self.auth_origins:
            raise ValueError('At least one explicit authentication Origin is required')
        for origin in self.auth_origins:
            parsed = urlsplit(origin)
            if (parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username
                    or parsed.password or parsed.path or parsed.query or parsed.fragment or '*' in origin):
                raise ValueError('Authentication origins must be exact HTTP(S) origins without paths')
        if self.app_env in ('staging', 'production'):
            if not self.cookie_secure or any(not value.startswith('https://') for value in self.auth_origins):
                raise ValueError('Staging/production requires Secure cookies and HTTPS origins')

    def validate_database(self) -> None:
        values = {'HOST': self.pg_host, 'PORT': self.pg_port, 'DATABASE': self.pg_database,
                  'USER': self.pg_user,
                  'PASSWORD': self.pg_password.get_secret_value() if self.pg_password else None}
        missing = [f'CREDITIQ_PG_{key}' for key, value in values.items()
                   if value is None or not str(value).strip()
                   or (str(value).startswith('<') and str(value).endswith('>'))]
        if missing:
            raise ValueError('Required database settings missing or placeholders: ' + ', '.join(missing))
        if self.db_hosting == 'supabase':
            if not self.pg_host.lower().endswith(('.supabase.com', '.supabase.co')):
                raise ValueError('Supabase hosting requires a Supabase database endpoint')
            if self.pg_sslmode not in {'require', 'verify-ca', 'verify-full'}:
                raise ValueError('Supabase connections require TLS')
        if self.pg_sslrootcert and not Path(self.pg_sslrootcert).is_file():
            raise ValueError('Configured PostgreSQL CA certificate file is missing')
        if self.app_env in ('staging', 'production'):
            if self.db_hosting != 'supabase' or self.pg_sslmode != 'verify-full':
                raise ValueError('Staging/production requires Supabase with TLS verify-full')
            if self.pg_user.split('.')[0] == 'postgres':
                raise ValueError('Staging/production requires a restricted runtime database role')

    @field_validator('release_ready', mode='before')
    @classmethod
    def parse_research_flag(cls, value):
        if isinstance(value, str) and value.lower() == 'false':
            return False
        return value

    @property
    def database_url(self) -> URL:
        # Structured URL preserves special characters and masks the password in repr.
        self.validate_database()
        query = {"sslmode": self.pg_sslmode}
        if self.pg_sslrootcert:
            query["sslrootcert"] = self.pg_sslrootcert
        return URL.create(
            "postgresql+psycopg", username=self.pg_user,
            password=self.pg_password.get_secret_value(), host=self.pg_host,
            port=self.pg_port, database=self.pg_database,
            query=query,
        )

    @property
    def migration_url(self) -> URL:
        if self.migration_database_url is None:
            if self.db_hosting == "supabase":
                raise ValueError("Set CREDITIQ_MIGRATION_DATABASE_URL to a direct or session connection")
            return self.database_url
        try:
            url = make_url(self.migration_database_url.get_secret_value())
        except (ArgumentError, ValueError):
            raise ValueError("Invalid migration database URL") from None
        if url.drivername != "postgresql+psycopg" or not url.host or not url.database:
            raise ValueError("Migration URL must specify postgresql+psycopg, host and database")
        # The operator must select a direct/session endpoint; transaction pooling is unsuitable for DDL tools.
        if self.db_hosting == "supabase" and url.query.get("sslmode") not in {"require", "verify-ca", "verify-full"}:
            raise ValueError("Supabase migration connections require TLS in the migration URL")
        if self.db_hosting == 'supabase' and (not url.host.lower().endswith(('.supabase.com', '.supabase.co'))
                or url.port == 6543):
            raise ValueError('Supabase migrations require a direct or session Supabase endpoint')
        if not url.username or not url.password:
            raise ValueError('Migration URL requires explicit operator credentials')
        if self.app_env in ('staging', 'production') and url.query.get('sslmode') != 'verify-full':
            raise ValueError('Staging/production migration connections require TLS verify-full')
        return url
