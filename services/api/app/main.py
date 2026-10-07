from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import text

from app.core.config import Settings
from app.core.startup_environment_validator import render_managed_https, validate_startup_environment
import json
from app.db.session import build_engine, build_session_factory
from app.auth.middleware import AuthSafetyMiddleware, TransportSafetyMiddleware
from app.routers.auth import router as auth_router, clear_cookies
from app.services.auth import AuthenticationError
from app.routers.applications import router as applications_router
from app.routers.admin import router as admin_router
from app.services.lite_model import LiteModel
from app.routers.installments import router as installments_router
from app.routers.planner import router as planner_router

logger = logging.getLogger('uvicorn.error')


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings if settings is not None else Settings()
    environment_summary = validate_startup_environment(settings)

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        engine = build_engine(settings)
        application.state.session_factory = build_session_factory(engine)
        try:
            try:
                with engine.connect() as connection:
                    connection.execute(text('SELECT 1'))
                    if settings.app_env in ('staging', 'production'):
                        elevated = connection.execute(text(
                            'SELECT rolsuper OR rolcreatedb OR rolcreaterole OR rolbypassrls OR rolreplication '
                            'FROM pg_roles WHERE rolname = current_user')).scalar_one()
                        if elevated:
                            raise RuntimeError('Runtime database role must not have administrative privileges')
            except SQLAlchemyError:
                logger.error('database_startup_failed')
                raise RuntimeError('Database startup validation failed') from None
            logger.info('database_startup_connected hosting=%s', settings.db_hosting)
            logger.info('startup_environment %s', json.dumps(environment_summary))
            application.state.lite_model = LiteModel() if settings.lite_enabled else None
            yield
        finally:
            engine.dispose()

    application = FastAPI(
        title="CreditIQ Research API", version="0.4.0",
        description="Research-only Lite scoring, owned applications and read-only administration.",
        lifespan=lifespan,
    )
    application.state.settings = settings
    application.include_router(auth_router)
    application.include_router(applications_router)
    application.include_router(admin_router)
    application.include_router(installments_router)
    application.include_router(planner_router)
    application.add_middleware(AuthSafetyMiddleware)
    application.add_middleware(CORSMiddleware, allow_origins=settings.auth_origins,
                               allow_credentials=True, allow_methods=['GET', 'POST', 'DELETE'],
                               allow_headers=['Content-Type', 'X-CSRF-Token', 'Idempotency-Key'])
    application.add_middleware(TransportSafetyMiddleware,
                              https_only=settings.app_env in ('staging', 'production'),
                              managed_https=render_managed_https(settings))

    @application.exception_handler(AuthenticationError)
    async def authentication_failed(request: Request, exc: AuthenticationError):
        response = JSONResponse({'detail': 'Authentication failed'}, status_code=401,
                                headers={'WWW-Authenticate': 'Bearer'})
        clear_cookies(response, settings)
        return response

    @application.exception_handler(RequestValidationError)
    async def invalid_input(request: Request, exc: RequestValidationError):
        # FastAPI's default includes rejected input; never echo passwords or tokens.
        errors = [{key: item[key] for key in ('type', 'loc', 'msg')} for item in exc.errors()]
        return JSONResponse({'detail': errors}, status_code=422)

    @application.exception_handler(SQLAlchemyError)
    async def database_failed(request: Request, exc: SQLAlchemyError):
        logger.error('database_request_failed type=%s', type(exc).__name__)
        return JSONResponse({'detail': 'Service temporarily unavailable'}, status_code=503)

    @application.get('/health/live', tags=['operations'])
    @application.get("/api/v1/health/live", tags=["operations"])
    def liveness() -> dict[str, str]:
        # Process liveness only: this must not imply database/model readiness.
        return {"status": "ok"}

    @application.get('/health/ready', tags=['operations'])
    @application.get('/api/v1/health/ready', tags=['operations'])
    def readiness(request: Request):
        try:
            with request.app.state.session_factory.kw['bind'].connect() as connection:
                connection.execute(text('SELECT 1'))
        except SQLAlchemyError:
            logger.warning('database_readiness_failed')
            return JSONResponse({'status': 'unavailable'}, status_code=503,
                                headers={'Cache-Control': 'no-store'})
        return JSONResponse({'status': 'ready'}, headers={'Cache-Control': 'no-store'})

    return application


app = create_app()

