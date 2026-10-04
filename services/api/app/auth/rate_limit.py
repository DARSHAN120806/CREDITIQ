"""PostgreSQL-backed rolling limits shared by all API workers."""
from datetime import timedelta
import uuid

from fastapi import HTTPException, Request
from sqlalchemy import func, select, text

from app.auth.security import keyed_digest, utcnow
from app.db.models import AuditEvent


def check_rate_limit(request: Request, account: str | None = None) -> None:
    settings = request.app.state.settings
    # Do not trust arbitrary X-Forwarded-For. Configure trusted proxy handling at the server.
    ip = request.client.host if request.client else 'unknown'
    scopes = [('ip:' + ip, settings.auth_ip_limit)]
    if account is not None:
        scopes.append(('account:' + account, settings.auth_account_limit))
    keys = [(uuid.UUID(bytes=keyed_digest(settings, 'rate', value)[:16]), limit) for value, limit in scopes]
    keys.sort(key=lambda pair: pair[0].int)
    cutoff = utcnow() - timedelta(seconds=settings.auth_window_seconds)
    with request.app.state.session_factory.begin() as db:
        for key, limit in keys:
            lock_id = int.from_bytes(key.bytes[:8], signed=True)
            db.execute(text('SELECT pg_advisory_xact_lock(:key)'), {'key': lock_id})
            count = db.scalar(select(func.count()).select_from(AuditEvent).where(
                AuditEvent.action == 'AUTH_RATE', AuditEvent.entity_id == key, AuditEvent.created_at >= cutoff))
            if count >= limit:
                raise HTTPException(429, 'Too many authentication attempts',
                                    headers={'Retry-After': str(settings.auth_window_seconds)})
        for key, _ in keys:
            db.add(AuditEvent(action='AUTH_RATE', entity_type='auth_scope', entity_id=key,
                              request_id=str(uuid.uuid4()), redacted_metadata_json={}))
