from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import Settings
from app.db.session import build_engine, build_session_factory
from app.auth.middleware import AuthSafetyMiddleware
from app.routers.auth import router as auth_router, clear_cookies
from app.services.auth import AuthenticationError
from app.routers.applications import router as applications_router
from app.routers.admin import router as admin_router
from app.services.lite_model import LiteModel
from app.routers.installments import router as installments_router
from app.routers.planner import router as planner_router


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings if settings is not None else Settings()
    settings.validate_auth()

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        application.state.lite_model = LiteModel() if settings.lite_enabled else None
        engine = build_engine(settings)
        application.state.session_factory = build_session_factory(engine)
        try:
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
        return JSONResponse({'detail': 'Service temporarily unavailable'}, status_code=503)

    @application.get("/api/v1/health/live", tags=["operations"])
    def liveness() -> dict[str, str]:
        # Process liveness only: this must not imply database/model readiness.
        return {"status": "ok"}

    return application


app = create_app()

