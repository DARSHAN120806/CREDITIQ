from collections.abc import Iterator

from fastapi import Request
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings


def build_engine(settings: Settings) -> Engine:
    # Creating an engine does not connect. No create_all or automatic migrations.
    return create_engine(
        settings.database_url, pool_pre_ping=True, hide_parameters=True,
        pool_size=settings.db_pool_size, max_overflow=settings.db_max_overflow,
        pool_timeout=30, connect_args={"connect_timeout": 5},
    )


def build_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_session(request: Request) -> Iterator[Session]:
    # Future services own explicit transaction/commit boundaries.
    with request.app.state.session_factory() as session:
        yield session
