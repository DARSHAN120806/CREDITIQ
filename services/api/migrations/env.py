"""Alembic environment using the same PostgreSQL settings as the application."""
from alembic import context
from sqlalchemy import create_engine, pool

from app.core.config import Settings
from app.db.base import Base
from app.db import models  # noqa: F401 -- register all mapped tables

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=Settings().migration_url, target_metadata=target_metadata,
        literal_binds=True, dialect_opts={"paramstyle": "named"}, compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    # Explicit connections support isolated migration tests and operator-owned
    # migration credentials without changing the application's restricted role.
    supplied = context.config.attributes.get('connection')
    if supplied is not None:
        context.configure(connection=supplied, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()
        return
    engine = create_engine(
        Settings().migration_url, poolclass=pool.NullPool, hide_parameters=True,
        connect_args={"connect_timeout": 5},
    )
    try:
        with engine.connect() as connection:
            context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
