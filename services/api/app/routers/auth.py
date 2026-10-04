from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response
import jwt
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import Principal, current_principal, require_csrf, require_permission
from app.auth.rate_limit import check_rate_limit
from app.auth.security import (ACCESS_COOKIE, CSRF_COOKIE, REFRESH_COOKIE, COOKIE_PATH,
    access_token, csrf_token, decode_access, utcnow, cookie_name, request_cookie)
from app.db.models import AuthSession
from app.db.session import get_session
from app.schemas.auth import Credentials, RegisterRequest, UserView, LoginView, SessionView, CsrfView
from app.services import auth as service
from app.services.users import create_user, user_view

router = APIRouter(prefix='/api/v1', tags=['authentication'])


def set_cookie(response, settings, name, value, max_age, *, httponly=True):
    response.set_cookie(cookie_name(settings, name), value, max_age=max_age, path=COOKIE_PATH,
                        httponly=httponly, secure=settings.cookie_secure, samesite='strict')


def clear_cookies(response, settings):
    for name in (ACCESS_COOKIE, REFRESH_COOKIE, CSRF_COOKIE):
        response.delete_cookie(cookie_name(settings, name), path=COOKIE_PATH, secure=settings.cookie_secure,
                               httponly=name != CSRF_COOKIE, samesite='strict')


def issue_response(request, response, db, issued):
    settings = request.app.state.settings
    token = access_token(settings, issued.user.id, issued.session_id, issued.expires_at)
    csrf = csrf_token(settings, issued.refresh)
    access_age = min(settings.access_token_minutes * 60, max(0, int((issued.expires_at - utcnow()).total_seconds())))
    set_cookie(response, settings, ACCESS_COOKIE, token, access_age)
    set_cookie(response, settings, REFRESH_COOKIE, issued.refresh,
               max(0, int((issued.expires_at - utcnow()).total_seconds())))
    set_cookie(response, settings, CSRF_COOKIE, csrf, 3600, httponly=False)
    return LoginView(**user_view(db, issued.user).model_dump(), csrf_token=csrf,
                      expires_in=access_age)


@router.get('/auth/csrf', response_model=CsrfView)
def get_csrf(request: Request, response: Response):
    settings = request.app.state.settings
    refresh = request_cookie(request, REFRESH_COOKIE)
    if len(refresh) > 128:
        raise HTTPException(400, 'Invalid cookie')
    token = csrf_token(settings, refresh)
    set_cookie(response, settings, CSRF_COOKIE, token, 3600, httponly=False)
    return CsrfView(csrf_token=token)


@router.post('/auth/register', status_code=202, dependencies=[Depends(require_csrf)])
def register(body: RegisterRequest, request: Request, db: Session = Depends(get_session)):
    check_rate_limit(request, body.email)
    create_user(db, email=body.email, password=body.password.get_secret_value(), full_name=body.full_name)
    # Same result for a duplicate address; neither response exposes an account identifier.
    return {'message': 'Registration processed. Sign in if the account is available.'}


@router.post('/auth/login', response_model=LoginView, dependencies=[Depends(require_csrf)])
def login(body: Credentials, request: Request, response: Response, db: Session = Depends(get_session)):
    check_rate_limit(request, body.email)
    issued = service.login(db, request.app.state.settings, body.email, body.password.get_secret_value())
    return issue_response(request, response, db, issued)


@router.post('/auth/refresh', response_model=LoginView, dependencies=[Depends(require_csrf)])
def refresh(request: Request, response: Response, db: Session = Depends(get_session)):
    check_rate_limit(request)
    issued = service.rotate(db, request_cookie(request, REFRESH_COOKIE))
    return issue_response(request, response, db, issued)


@router.post('/auth/logout', status_code=204, dependencies=[Depends(require_csrf)])
def logout(request: Request, response: Response, db: Session = Depends(get_session)):
    identity = None
    try:
        claims = decode_access(request.app.state.settings, request_cookie(request, ACCESS_COOKIE))
        identity = UUID(claims['sub']), UUID(claims['sid'])
    except jwt.InvalidTokenError:
        pass
    service.logout(db, request_cookie(request, REFRESH_COOKIE), identity)
    clear_cookies(response, request.app.state.settings)


@router.get('/me', response_model=UserView)
def me(principal: Principal = Depends(current_principal), db: Session = Depends(get_session)):
    return user_view(db, principal.user)


@router.get('/auth/sessions', response_model=list[SessionView])
def sessions(principal: Principal = Depends(require_permission('sessions:manage')),
             db: Session = Depends(get_session)):
    rows = db.scalars(select(AuthSession).where(AuthSession.user_id == principal.user.id,
         AuthSession.revoked_at.is_(None), AuthSession.expires_at > utcnow()).order_by(AuthSession.created_at.desc())).all()
    return [SessionView(id=row.id, created_at=row.created_at, expires_at=row.expires_at,
                        current=row.id == principal.session.id) for row in rows]


@router.delete('/auth/sessions/{session_id}', status_code=204, dependencies=[Depends(require_csrf)])
def revoke(session_id: UUID, request: Request, response: Response,
           principal: Principal = Depends(require_permission('sessions:manage')),
           db: Session = Depends(get_session)):
    if not service.revoke_session(db, principal.user.id, session_id):
        raise HTTPException(404, 'Session not found')
    if session_id == principal.session.id:
        clear_cookies(response, request.app.state.settings)


@router.post('/auth/logout-all', status_code=204, dependencies=[Depends(require_csrf)])
def logout_all(request: Request, response: Response,
               principal: Principal = Depends(require_permission('sessions:manage')),
               db: Session = Depends(get_session)):
    service.revoke_all(db, principal.user.id)
    clear_cookies(response, request.app.state.settings)
