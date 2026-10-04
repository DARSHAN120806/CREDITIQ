from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.dependencies import ADMIN_PERMISSIONS, effective_permissions
from app.auth.security import hash_password
from app.db.models import AuditEvent, User, UserProfile
from app.schemas.auth import UserView
import uuid


def create_user(db: Session, *, email: str, password: str, full_name: str,
                role: str = 'USER', permissions=()) -> User | None:
    """Only trusted operators can pass ADMIN; public registration passes no privileges."""
    if role not in ('USER', 'ADMIN') or set(permissions) - ADMIN_PERMISSIONS or (role == 'USER' and permissions):
        raise ValueError('Invalid role/permissions')
    encoded = hash_password(password)  # also performed for duplicates; never store plaintext
    user = User(normalized_email=email, password_hash=encoded, role=role,
                permissions=sorted(set(permissions)), account_status='ACTIVE')
    try:
        db.add(user)
        db.flush()
        db.add(UserProfile(user_id=user.id, full_name=full_name))
        db.add(AuditEvent(actor_id=user.id, action='USER_CREATED', entity_type='user',
                          entity_id=user.id, request_id=str(uuid.uuid4()),
                          redacted_metadata_json={'role': role}))
        db.commit()
    except IntegrityError as error:
        db.rollback()
        if getattr(error.orig.diag, 'constraint_name', '') == 'uq_users_normalized_email':
            return None
        raise
    return user


def user_view(db: Session, user: User) -> UserView:
    name = db.scalar(select(UserProfile.full_name).where(UserProfile.user_id == user.id))
    return UserView(id=user.id, email=user.normalized_email, full_name=name,
                    role=user.role, permissions=sorted(effective_permissions(user)))
