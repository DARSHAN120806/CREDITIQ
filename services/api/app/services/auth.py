from dataclasses import dataclass
from datetime import datetime, timedelta
import re
import secrets
import uuid

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.auth.security import HASHER, digest_token, hash_password, utcnow, verify_password
from app.core.config import Settings
from app.db.models import AuditEvent, AuthSession, User


class AuthenticationError(Exception):
    """Deliberately contains no credential/account-existence information."""


@dataclass(frozen=True)
class SessionTokens:
    user: User
    session_id: uuid.UUID
    refresh: str
    expires_at: datetime


def audit(db, user_id, action, entity_id):
    db.add(AuditEvent(actor_id=user_id, action=action, entity_type='auth_session',
                      entity_id=entity_id, request_id=str(uuid.uuid4()), redacted_metadata_json={}))


def lock_user(db, user_id):
    # All rotations/revocations take this lock first. Never lock a session then a user.
    return db.scalar(select(User).where(User.id == user_id).with_for_update()
                     .execution_options(populate_existing=True))


def revoke_family(db, user_id, family_id):
    db.execute(update(AuthSession).where(AuthSession.user_id == user_id,
               AuthSession.token_family_id == family_id, AuthSession.revoked_at.is_(None))
               .values(revoked_at=func.clock_timestamp()))


def new_session(db, user, family_id, expires_at):
    raw = secrets.token_urlsafe(48)
    row = AuthSession(id=uuid.uuid4(), user_id=user.id, token_family_id=family_id,
                      hashed_refresh_token=digest_token(raw), expires_at=expires_at)
    db.add(row)
    db.flush()
    return SessionTokens(user, row.id, raw, expires_at)


def login(db: Session, settings: Settings, email: str, password: str) -> SessionTokens:
    user = db.scalar(select(User).where(User.normalized_email == email))
    encoded = user.password_hash if user else None
    valid = verify_password(password, encoded)
    if user is None or not valid:
        raise AuthenticationError()
    user = lock_user(db, user.id)
    if user.account_status != 'ACTIVE' or user.password_hash != encoded:
        raise AuthenticationError()
    if HASHER.check_needs_rehash(encoded):
        user.password_hash = hash_password(password)
    # Bound concurrent device sessions; rotation itself does not extend absolute lifetime.
    active = db.scalars(select(AuthSession).where(AuthSession.user_id == user.id,
        AuthSession.revoked_at.is_(None), AuthSession.expires_at > utcnow()).order_by(AuthSession.created_at)).all()
    for row in active[:-9]:
        revoke_family(db, user.id, row.token_family_id)
    issued = new_session(db, user, uuid.uuid4(), utcnow() + timedelta(days=settings.refresh_token_days))
    audit(db, user.id, 'LOGIN', issued.session_id)
    db.commit()
    return issued


def refresh_lookup(db, raw):
    if not re.fullmatch(r'[A-Za-z0-9_-]{64}', raw):
        return None
    return db.execute(select(AuthSession.id, AuthSession.user_id).where(
        AuthSession.hashed_refresh_token == digest_token(raw))).one_or_none()


def rotate(db: Session, raw: str) -> SessionTokens:
    found = refresh_lookup(db, raw)
    if found is None:
        raise AuthenticationError()
    user = lock_user(db, found.user_id)
    row = db.scalar(select(AuthSession).where(AuthSession.id == found.id).with_for_update()
                    .execution_options(populate_existing=True))
    if row.revoked_at is not None:
        # Persist revocation before returning 401; a request rollback must not undo detection.
        revoke_family(db, user.id, row.token_family_id)
        audit(db, user.id, 'REFRESH_REPLAY', row.id)
        db.commit()
        raise AuthenticationError()
    if row.expires_at <= utcnow() or user.account_status != 'ACTIVE':
        revoke_family(db, user.id, row.token_family_id)
        db.commit()
        raise AuthenticationError()
    # Persist revocation using the same clock that wrote created_at. Application hosts
    # can be slightly behind PostgreSQL and violate ck_auth_sessions_revocation_time.
    row.revoked_at = db.scalar(select(func.clock_timestamp()))
    issued = new_session(db, user, row.token_family_id, row.expires_at)
    audit(db, user.id, 'REFRESH_ROTATED', issued.session_id)
    db.commit()
    return issued


def logout(db: Session, raw: str, access_identity: tuple | None = None):
    found = refresh_lookup(db, raw)
    if found is None and access_identity is not None:
        uid, sid = access_identity
        found = db.execute(select(AuthSession.id, AuthSession.user_id).where(
            AuthSession.id == sid, AuthSession.user_id == uid)).one_or_none()
    if found is not None:
        lock_user(db, found.user_id)
        row = db.get(AuthSession, found.id, populate_existing=True)
        revoke_family(db, found.user_id, row.token_family_id)
        audit(db, found.user_id, 'LOGOUT', found.id)
        db.commit()


def revoke_session(db: Session, user_id, session_id) -> bool:
    lock_user(db, user_id)
    row = db.scalar(select(AuthSession).where(AuthSession.id == session_id, AuthSession.user_id == user_id))
    if row is None:
        return False
    revoke_family(db, user_id, row.token_family_id)
    audit(db, user_id, 'SESSION_REVOKED', row.id)
    db.commit()
    return True


def revoke_all(db: Session, user_id):
    lock_user(db, user_id)
    db.execute(update(AuthSession).where(AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None))
               .values(revoked_at=utcnow()))
    audit(db, user_id, 'ALL_SESSIONS_REVOKED', user_id)
    db.commit()
