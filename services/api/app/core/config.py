"""Typed environment settings shared by FastAPI and Alembic."""
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL

API_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="CREDITIQ_", env_file=API_ROOT / ".env",
        env_file_encoding="utf-8", extra="ignore",
    )

    app_env: Literal["development", "test", "staging", "production"] = "development"
    mode: Literal["RESEARCH_ONLY"] = "RESEARCH_ONLY"
    release_ready: Literal[False] = False
    pg_host: str = Field(default="localhost", min_length=1)
    pg_port: int = Field(default=5432, ge=1, le=65535)
    pg_database: str = Field(default="creditiq", min_length=1)
    pg_user: str = Field(default="creditiq", min_length=1)
    pg_password: SecretStr = SecretStr("")
    pg_sslmode: Literal["disable", "allow", "prefer", "require", "verify-ca", "verify-full"] = "prefer"
    db_pool_size: int = Field(default=5, ge=1)
    db_max_overflow: int = Field(default=5, ge=0)
    lite_enabled: bool = True
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

    @field_validator('release_ready', mode='before')
    @classmethod
    def parse_research_flag(cls, value):
        if isinstance(value, str) and value.lower() == 'false':
            return False
        return value

    @property
    def database_url(self) -> URL:
        # Structured URL preserves special characters and masks the password in repr.
        return URL.create(
            "postgresql+psycopg", username=self.pg_user,
            password=self.pg_password.get_secret_value(), host=self.pg_host,
            port=self.pg_port, database=self.pg_database,
            query={"sslmode": self.pg_sslmode},
        )
