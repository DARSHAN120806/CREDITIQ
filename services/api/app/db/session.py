from collections.abc import Iterator

from fastapi import Request
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings


def build_engine(settings: Settings) -> Engine:
    # Creating an engine does not connect. No create_all or automatic migrations.
    connect_args = {"connect_timeout": settings.db_connect_timeout}
    if settings.pg_connection_mode == "transaction":
        # Supavisor transaction pooling does not support psycopg prepared statements.
        connect_args["prepare_threshold"] = None
    engine = create_engine(
        settings.database_url, pool_pre_ping=True, hide_parameters=True,
        pool_size=settings.db_pool_size, max_overflow=settings.db_max_overflow,
        pool_timeout=settings.db_pool_timeout, pool_recycle=settings.db_pool_recycle,
        connect_args=connect_args,
    )

    def transaction_timeouts(connection):
        # Poolers may ignore libpq startup options. SET LOCAL also survives transaction
        # pooling correctly: each checkout/transaction receives the configured limits.
        connection.exec_driver_sql(f"SET LOCAL statement_timeout = '{settings.db_statement_timeout_ms}ms'")
        connection.exec_driver_sql(f"SET LOCAL lock_timeout = '{settings.db_lock_timeout_ms}ms'")

    event.listen(engine, 'begin', transaction_timeouts)
    return engine


def build_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_session(request: Request) -> Iterator[Session]:
    # Future services own explicit transaction/commit boundaries.
    with request.app.state.session_factory() as session:
        yield session
