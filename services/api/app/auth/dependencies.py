from dataclasses import dataclass
import hmac
from uuid import UUID

from fastapi import Depends, HTTPException, Request
import jwt
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.security import ACCESS_COOKIE, CSRF_COOKIE, REFRESH_COOKIE, decode_access, utcnow, valid_csrf, request_cookie
from app.db.models import AuthSession, User
from app.db.session import get_session

USER_PERMISSIONS = frozenset({'profile:read', 'sessions:manage', 'applications:own'})
ADMIN_PERMISSIONS = frozenset({'applications:review', 'analytics:read', 'reports:read',
                               'models:manage', 'policies:manage', 'policies:approve', 'audit:read'})


def effective_permissions(user: User) -> frozenset[str]:
    assigned = {p for p in user.permissions if isinstance(p, str)}
    return USER_PERMISSIONS | (assigned & ADMIN_PERMISSIONS if user.role == 'ADMIN' else frozenset())


@dataclass(frozen=True)
class Principal:
    user: User
    session: AuthSession


def unauthorized():
    return HTTPException(401, 'Authentication required', headers={'WWW-Authenticate': 'Bearer'})


def require_csrf(request: Request) -> None:
    settings = request.app.state.settings
    origin = request.headers.get('origin')
    supplied = request.headers.get('x-csrf-token', '')
    cookie = request_cookie(request, CSRF_COOKIE)
    if (origin not in settings.auth_origins or not cookie or not supplied
            or len(supplied) > 256 or len(cookie) > 256 or not supplied.isascii() or not cookie.isascii()
            or not hmac.compare_digest(cookie, supplied)
            or not valid_csrf(settings, supplied, request_cookie(request, REFRESH_COOKIE))):
        raise HTTPException(403, 'CSRF validation failed')


def current_principal(request: Request, db: Session = Depends(get_session)) -> Principal:
    try:
        payload = decode_access(request.app.state.settings, request_cookie(request, ACCESS_COOKIE))
    except jwt.InvalidTokenError:
        raise unauthorized() from None
    result = db.execute(select(User, AuthSession).join(AuthSession, AuthSession.user_id == User.id)
                        .where(User.id == UUID(payload['sub']), AuthSession.id == UUID(payload['sid']),
                               User.account_status == 'ACTIVE', AuthSession.revoked_at.is_(None),
                               AuthSession.expires_at > utcnow())).one_or_none()
    if result is None:
        raise unauthorized()
    return Principal(result[0], result[1])


def require_role(role: str):
    if role not in ('USER', 'ADMIN'):
        raise ValueError('Unknown role')

    def check(principal: Principal = Depends(current_principal)) -> Principal:
        if principal.user.role != role:
            raise HTTPException(403, 'Insufficient role')
        return principal
    return check


def require_permission(permission: str):
    if permission not in USER_PERMISSIONS | ADMIN_PERMISSIONS:
        raise ValueError('Unknown permission')

    def check(principal: Principal = Depends(current_principal)) -> Principal:
        if permission not in effective_permissions(principal.user):
            raise HTTPException(403, 'Insufficient permission')
        return principal
    return check
