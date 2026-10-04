"""Immutable user-owned repayment history, separate from model predictions."""
import sqlalchemy as sa
from app.db.base import Base
from .schema import table, uid, col, js, ck, enum, positive, currency, money

class InstallmentImport(Base):
    __table__ = table('installment_imports', uid('user_id', 'users.id'),
        col('idempotency_key'), col('content_hash', sa.String(64)), col('label'),
        col('source_kind'), col('currency'), col('as_of', sa.Date),
        col('window_start', sa.Date), js('coverage_json'),
        sa.UniqueConstraint('user_id', 'idempotency_key'),
        enum('source_kind', 'USER_DECLARED DEMO'), currency(),
        ck('window_order', 'window_start <= as_of'),
        sa.Index('ix_installment_imports_owner_created', 'user_id', 'created_at'))

class InstallmentSchedule(Base):
    __table__ = table('installment_schedules', uid('import_id', 'installment_imports.id'),
        col('account_ref'), col('installment_ref'), col('schedule_version'),
        col('due_date', sa.Date), col('amount', money), positive('amount'),
        sa.UniqueConstraint('import_id', 'account_ref', 'installment_ref'),
        sa.UniqueConstraint('id', 'import_id'))

class InstallmentPayment(Base):
    __table__ = table('installment_payments', uid('import_id', 'installment_imports.id'),
        uid('schedule_id'), col('event_ref'), col('paid_date', sa.Date),
        col('amount', money), positive('amount', zero=True),
        sa.ForeignKeyConstraint(['schedule_id', 'import_id'],
            ['installment_schedules.id', 'installment_schedules.import_id']),
        sa.UniqueConstraint('import_id', 'event_ref'))

class InstallmentAnalysis(Base):
    __table__ = table('installment_analyses', uid('import_id', 'installment_imports.id'),
        col('calculation_version'), js('result_json'),
        sa.UniqueConstraint('import_id', 'calculation_version'))
