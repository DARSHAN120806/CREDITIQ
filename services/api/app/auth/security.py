from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import secrets
import threading
import time
import uuid

from argon2 import PasswordHasher, Type
from argon2.exceptions import InvalidHashError, VerificationError
import jwt

from app.core.config import Settings

ACCESS_COOKIE = 'creditiq_access'
REFRESH_COOKIE = 'creditiq_refresh'
CSRF_COOKIE = 'creditiq_csrf'
COOKIE_PATH = '/'
HASHER = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=2, type=Type.ID)
HASH_SLOTS = threading.BoundedSemaphore(4)
DUMMY_HASH = HASHER.hash(secrets.token_urlsafe(32))


def utcnow():
    return datetime.now(timezone.utc)


def hash_password(password: str) -> str:
    with HASH_SLOTS:
        return HASHER.hash(password)


def verify_password(password: str, encoded: str | None) -> bool:
    try:
        with HASH_SLOTS:
            return HASHER.verify(encoded or DUMMY_HASH, password)
    except (VerificationError, InvalidHashError):
        return False


def digest_token(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def keyed_digest(settings: Settings, purpose: str, value: str) -> bytes:
    return hmac.digest(settings.jwt_secret.get_secret_value().encode(),
                       f'{purpose}\0{value}'.encode(), 'sha256')


def cookie_name(settings: Settings, name: str) -> str:
    # __Host- prevents sibling subdomains from planting a Domain-scoped auth cookie.
    return '__Host-' + name if settings.cookie_secure else name


def request_cookie(request, name: str) -> str:
    return request.cookies.get(cookie_name(request.app.state.settings, name), '')


def access_token(settings: Settings, user_id: uuid.UUID, session_id: uuid.UUID, expires_at=None) -> str:
    now = utcnow()
    expiry = now + timedelta(minutes=settings.access_token_minutes)
    if expires_at is not None:
        expiry = min(expiry, expires_at)
    return jwt.encode({'sub': str(user_id), 'sid': str(session_id), 'jti': str(uuid.uuid4()),
                       'iss': settings.jwt_issuer, 'aud': settings.jwt_audience, 'token_use': 'access',
                       'iat': now, 'nbf': now, 'exp': expiry},
                      settings.jwt_secret.get_secret_value(), algorithm='HS256')


def decode_access(settings: Settings, token: str) -> dict:
    if len(token) > 4096:
        raise jwt.InvalidTokenError('Invalid access token')
    payload = jwt.decode(token, settings.jwt_secret.get_secret_value(), algorithms=['HS256'],
                         issuer=settings.jwt_issuer, audience=settings.jwt_audience,
                         options={'require': ['sub', 'sid', 'jti', 'iss', 'aud', 'iat', 'nbf', 'exp', 'token_use']})
    if payload['token_use'] != 'access':
        raise jwt.InvalidTokenError('Wrong token purpose')
    try:
        uuid.UUID(payload['sub']); uuid.UUID(payload['sid']); uuid.UUID(payload['jti'])
    except (ValueError, TypeError, AttributeError) as error:
        raise jwt.InvalidTokenError('Invalid token identities') from error
    return payload


def csrf_token(settings: Settings, refresh: str = '') -> str:
    body = f'{int(time.time())}.{secrets.token_urlsafe(24)}'
    signature = keyed_digest(settings, 'csrf', f'{body}.{digest_token(refresh)}').hex()
    return f'{body}.{signature}'


def valid_csrf(settings: Settings, token: str, refresh: str = '') -> bool:
    if len(token) > 256 or len(refresh) > 128:
        return False
    try:
        issued, nonce, signature = token.split('.')
        age = time.time() - int(issued)
        if not 0 <= age <= 3600 or not nonce:
            return False
        expected = keyed_digest(settings, 'csrf', f'{issued}.{nonce}.{digest_token(refresh)}').hex()
        return hmac.compare_digest(signature, expected)
    except (ValueError, TypeError):
        return False
