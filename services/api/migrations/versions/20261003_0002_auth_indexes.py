"""Authentication lookup indexes; no table or historical migration replacement."""
from alembic import op
import sqlalchemy as sa

revision = '20261003_0002'
down_revision = '20261003_0001'
branch_labels = None
depends_on = None


def upgrade():
    op.create_index('ix_auth_sessions_user_family', 'auth_sessions', ['user_id', 'token_family_id'])
    op.create_index('ix_auth_sessions_active_expiry', 'auth_sessions', ['user_id', 'expires_at'],
                    postgresql_where=sa.text('revoked_at IS NULL'))
    op.create_index('ix_audit_auth_rate', 'audit_events', ['action', 'entity_id', 'created_at'])


def downgrade():
    op.drop_index('ix_audit_auth_rate', table_name='audit_events')
    op.drop_index('ix_auth_sessions_active_expiry', table_name='auth_sessions')
    op.drop_index('ix_auth_sessions_user_family', table_name='auth_sessions')
