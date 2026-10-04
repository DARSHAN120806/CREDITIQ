"""PostgreSQL storage contracts. No routes, authentication or scoring behavior.

Explicit Table-backed declarative classes keep database constraints visible together.
Denormalized identity columns exist only to enforce composite provenance foreign keys.
"""
import uuid

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.db.base import Base


def col(name, kind=sa.Text, *, nullable=False, **kw):
    return sa.Column(name, kind, nullable=nullable, **kw)


def uid(name, target=None, *, nullable=False):
    args = [sa.ForeignKey(target)] if target else []
    return sa.Column(name, UUID(as_uuid=True), *args, nullable=nullable)


def stamp(name, *, nullable=False, now=False):
    return col(name, sa.DateTime(timezone=True), nullable=nullable,
               **({'server_default': sa.text('now()')} if now else {}))


def js(name, *, array=False):
    return col(name, JSONB, server_default=sa.text("'[]'::jsonb" if array else "'{}'::jsonb"))


def ck(name, expression):
    return sa.CheckConstraint(expression, name=name)


def enum(name, values):
    return ck(name + '_values', f"{name} IN ({', '.join(repr(v) for v in values.split())})")


def bounds(name, lower, upper):
    return ck(name + '_bounds', f'{name} >= {lower} AND {name} <= {upper}')


def positive(name, zero=False):
    # PostgreSQL considers NaN above Infinity, so this excludes both explicitly.
    return ck(name + '_finite', f"{name} {'>=' if zero else '>'} 0 AND {name} < 'Infinity'")


def currency():
    return ck('currency_format', "currency ~ '^[A-Z]{3}$'")


def fk(local, remote, name=None, **kw):
    return sa.ForeignKeyConstraint(local.split(), remote.split(), name=name, **kw)


def table(name, *items, identity=True, created=True):
    common = [sa.Column('id', UUID(as_uuid=True), primary_key=True,
                        default=uuid.uuid4, server_default=sa.text('gen_random_uuid()'))] if identity else []
    if created:
        common.append(stamp('created_at', now=True))
    checks = []
    for item in items:
        if isinstance(item, sa.Column) and isinstance(item.type, JSONB):
            array = str(item.server_default.arg).startswith("'[]'")
            checks.append(ck(item.name + '_shape', f"jsonb_typeof({item.name}) = '{'array' if array else 'object'}'"))
    return sa.Table(name, Base.metadata, *common, *items, *checks)


money = sa.Numeric(20, 2)
rate = sa.Numeric(12, 8)


class User(Base):
    __table__ = table('users', col('normalized_email'), col('password_hash'),
        col('role', server_default='USER'), col('account_status', server_default='ACTIVE'),
        js('permissions', array=True), stamp('updated_at', now=True),
        sa.UniqueConstraint('normalized_email'),
        ck('normalized_email_format', "normalized_email = lower(btrim(normalized_email)) AND position('@' in normalized_email) > 1"),
        ck('password_hash_nonempty', "length(password_hash) > 0"),
        enum('role', 'USER ADMIN'), enum('account_status', 'ACTIVE DISABLED CLOSED'))


class UserProfile(Base):
    __table__ = table('user_profiles',
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id'), primary_key=True),
        col('full_name'), col('birth_date', sa.Date, nullable=True), js('contact_json'),
        stamp('updated_at', now=True), identity=False)


class AuthSession(Base):
    __table__ = table('auth_sessions', uid('user_id', 'users.id'), col('hashed_refresh_token'),
        uid('token_family_id'), stamp('expires_at'), stamp('revoked_at', nullable=True),
        sa.UniqueConstraint('hashed_refresh_token'), ck('expires_after_creation', 'expires_at > created_at'),
        ck('revocation_time', 'revoked_at IS NULL OR revoked_at >= created_at'),
        sa.Index('ix_auth_sessions_user_id', 'user_id'),
        sa.Index('ix_auth_sessions_user_family', 'user_id', 'token_family_id'),
        sa.Index('ix_auth_sessions_active_expiry', 'user_id', 'expires_at', postgresql_where=sa.text('revoked_at IS NULL')))


class LoanApplication(Base):
    __table__ = table('loan_applications', uid('user_id', 'users.id'),
        col('current_version', sa.Integer, server_default='1'), col('product_code', server_default='CASH_INSTALLMENT_V1'),
        col('currency', sa.String(3)), col('requested_amount', money),
        col('workflow_status', server_default='DRAFT'), uid('current_decision_id', nullable=True),
        stamp('submitted_at', nullable=True), stamp('updated_at', now=True),
        sa.UniqueConstraint('id', 'user_id'), positive('requested_amount'), currency(),
        ck('current_version_positive', 'current_version > 0'),
        enum('workflow_status', 'DRAFT SUBMITTED PROCESSING PENDING_DATA MANUAL_REVIEW DECIDED WITHDRAWN'),
        enum('product_code', 'CASH_INSTALLMENT_V1'),
        fk('id current_version', 'application_versions.application_id application_versions.version',
           'fk_application_current_version', use_alter=True, deferrable=True, initially='DEFERRED'),
        fk('current_decision_id id current_version', 'decisions.id decisions.application_id decisions.application_version_number',
           'fk_application_current_decision', use_alter=True, deferrable=True, initially='DEFERRED'),
        sa.Index('ix_applications_user_created', 'user_id', 'created_at'),
        sa.Index('ix_applications_status_submitted', 'workflow_status', 'submitted_at'))


class ApplicationVersion(Base):
    __table__ = table('application_versions', uid('application_id', 'loan_applications.id'),
        col('version', sa.Integer), col('input_schema_version'), js('immutable_input_json'),
        col('input_hash', sa.String(64)), stamp('as_of'), uid('created_by', 'users.id'),
        sa.UniqueConstraint('application_id', 'version'), sa.UniqueConstraint('id', 'application_id'),
        sa.UniqueConstraint('id', 'application_id', 'version'), ck('version_positive', 'version > 0'))


class LoanQuote(Base):
    __table__ = table('loan_quotes', uid('application_version_id', 'application_versions.id'),
        col('product_version'), col('principal', money), col('term_months', sa.Integer),
        col('annual_rate', rate), col('monthly_payment', money), js('fees_json'),
        col('currency', sa.String(3)), stamp('expires_at'), positive('principal'),
        positive('monthly_payment'), positive('annual_rate', zero=True), currency(),
        ck('term_positive', 'term_months > 0'), ck('expiry', 'expires_at > created_at'),
        sa.Index('ix_loan_quotes_application_version', 'application_version_id'))


class DataConsent(Base):
    __table__ = table('data_consents', uid('application_id'), uid('user_id'), col('purpose'),
        col('source_scope'), col('consent_version'), stamp('granted_at'), stamp('revoked_at', nullable=True),
        fk('application_id user_id', 'loan_applications.id loan_applications.user_id'),
        sa.UniqueConstraint('id', 'application_id'), ck('revocation_order', 'revoked_at IS NULL OR revoked_at >= granted_at'))


class SourceSnapshot(Base):
    __table__ = table('source_snapshots', uid('application_version_id'), uid('application_id'),
        col('source_type'), col('state'), stamp('source_as_of'), stamp('fetched_at'),
        col('schema_version'), js('coverage_json'), col('object_key', nullable=True),
        col('content_hash', sa.String(64), nullable=True), uid('consent_id', nullable=True),
        fk('application_version_id application_id', 'application_versions.id application_versions.application_id'),
        fk('consent_id application_id', 'data_consents.id data_consents.application_id'),
        sa.UniqueConstraint('id', 'application_version_id'), sa.UniqueConstraint('id', 'application_id'),
        enum('state', 'COMPLETE CONFIRMED_EMPTY UNAVAILABLE INVALID'),
        ck('coverage_time', 'source_as_of <= fetched_at'))


class FeatureSnapshot(Base):
    __table__ = table('feature_snapshots', uid('application_version_id', 'application_versions.id'),
        col('variant'), col('feature_schema_version'), js('feature_values_json'),
        col('ordered_feature_hash', sa.String(64)), js('quality_flags_json', array=True), stamp('as_of'),
        sa.UniqueConstraint('id', 'application_version_id'),
        sa.UniqueConstraint('id', 'application_version_id', 'variant'), enum('variant', 'LITE FULL'))


class FeatureSnapshotSource(Base):
    __table__ = table('feature_snapshot_sources',
        sa.Column('feature_snapshot_id', UUID(as_uuid=True), primary_key=True),
        sa.Column('source_snapshot_id', UUID(as_uuid=True), primary_key=True), uid('application_version_id'),
        fk('feature_snapshot_id application_version_id', 'feature_snapshots.id feature_snapshots.application_version_id'),
        fk('source_snapshot_id application_version_id', 'source_snapshots.id source_snapshots.application_version_id'),
        identity=False, created=False)


class ModelVersion(Base):
    __table__ = table('model_versions', col('release_name'), col('variant'), col('feature_schema_version'),
        col('target_definition_version'), col('training_manifest_key'), col('artifact_key'),
        col('sha256', sa.String(64)), col('calibration_version'), col('runtime_lock_hash', sa.String(64)),
        js('metrics_json'), col('lifecycle_status', server_default='REGISTERED'),
        col('mode', server_default='RESEARCH_ONLY'), col('release_ready', sa.Boolean, server_default=sa.false()),
        sa.UniqueConstraint('release_name'), sa.UniqueConstraint('id', 'variant'), enum('variant', 'LITE FULL'),
        enum('lifecycle_status', 'REGISTERED VALIDATED RETIRED'), enum('mode', 'RESEARCH_ONLY'),
        ck('research_release', 'release_ready = false'))


class ModelDeployment(Base):
    __table__ = table('model_deployments', col('product_code'), col('variant'), uid('model_version_id'),
        stamp('activated_at'), stamp('retired_at', nullable=True),
        fk('model_version_id variant', 'model_versions.id model_versions.variant'),
        enum('variant', 'LITE FULL'), ck('retirement_order', 'retired_at IS NULL OR retired_at >= activated_at'),
        sa.Index('uq_model_deployment_active', 'product_code', 'variant', unique=True,
                 postgresql_where=sa.text('retired_at IS NULL')))


class ScoringJob(Base):
    __table__ = table('scoring_jobs', uid('application_version_id', 'application_versions.id'),
        col('variant_requested', server_default='AUTO'), col('status', server_default='QUEUED'),
        uid('model_version_id', 'model_versions.id', nullable=True), col('idempotency_key'),
        col('request_body_hash', sa.String(64)), col('error_code', nullable=True),
        col('attempts', sa.Integer, server_default='0'), stamp('completed_at', nullable=True),
        sa.UniqueConstraint('application_version_id', 'idempotency_key'),
        sa.UniqueConstraint('id', 'application_version_id', 'model_version_id'),
        enum('variant_requested', 'AUTO LITE FULL'), enum('status', 'QUEUED RUNNING SUCCEEDED FAILED PENDING_DATA'),
        ck('attempts_nonnegative', 'attempts >= 0'), sa.Index('ix_jobs_status_created', 'status', 'created_at'))


class Prediction(Base):
    __table__ = table('predictions', uid('scoring_job_id'), uid('application_version_id'),
        uid('feature_snapshot_id'), uid('model_version_id'), col('variant'),
        col('raw_positive_output', sa.Double), col('calibrated_pd', sa.Double),
        js('quality_flags_json', array=True), col('verification_status'), stamp('scored_at'),
        sa.UniqueConstraint('scoring_job_id'), sa.UniqueConstraint('id', 'application_version_id'),
        fk('scoring_job_id application_version_id model_version_id', 'scoring_jobs.id scoring_jobs.application_version_id scoring_jobs.model_version_id'),
        fk('feature_snapshot_id application_version_id variant', 'feature_snapshots.id feature_snapshots.application_version_id feature_snapshots.variant'),
        fk('model_version_id variant', 'model_versions.id model_versions.variant'), enum('variant', 'LITE FULL'),
        bounds('calibrated_pd', 0, 1),
        ck('raw_output_finite', "raw_positive_output > '-Infinity'::float8 AND raw_positive_output < 'Infinity'::float8"),
        enum('verification_status', 'UNVERIFIED PARTIAL VERIFIED'),
        sa.Index('ix_predictions_version_scored', 'application_version_id', 'scored_at'))


class RiskScore(Base):
    __table__ = table('risk_scores', uid('prediction_id', 'predictions.id'), col('score_policy_version'),
        col('risk_score', sa.Double), col('risk_band'), col('reference_percentile', sa.Double, nullable=True),
        col('reference_cohort_version', nullable=True), col('credit_health_index', sa.Double),
        sa.UniqueConstraint('prediction_id', 'score_policy_version'), bounds('risk_score', 0, 100),
        bounds('reference_percentile', 0, 100), bounds('credit_health_index', 0, 100),
        enum('risk_band', 'Low Medium High'),
        ck('reference_pair', '(reference_percentile IS NULL) = (reference_cohort_version IS NULL)'))


class PolicyVersion(Base):
    __table__ = table('policy_versions', col('version'), col('product_code'), col('variant'),
        col('mode', server_default='SANDBOX'), col('approve_below', sa.Double, nullable=True),
        col('reject_at', sa.Double, nullable=True), js('band_thresholds_json'), js('affordability_rules_json'),
        col('validation_report_key', nullable=True), uid('approved_by', 'users.id', nullable=True), stamp('effective_from'),
        sa.UniqueConstraint('version'), enum('variant', 'LITE FULL'), enum('mode', 'SANDBOX SHADOW'),
        ck('threshold_order', '(approve_below IS NULL AND reject_at IS NULL) OR '
           '(approve_below IS NOT NULL AND reject_at IS NOT NULL AND 0 < approve_below AND approve_below < reject_at AND reject_at < 1)'))


class Decision(Base):
    __table__ = table('decisions', uid('application_version_id'), uid('application_id'),
        col('application_version_number', sa.Integer), uid('prediction_id', nullable=True),
        uid('policy_version_id', 'policy_versions.id'), col('kind'), col('status'),
        js('reason_codes_json', array=True), js('affordability_snapshot_json'),
        uid('actor_id', 'users.id', nullable=True), uid('supersedes_id', nullable=True),
        fk('application_version_id application_id application_version_number', 'application_versions.id application_versions.application_id application_versions.version'),
        fk('prediction_id application_version_id', 'predictions.id predictions.application_version_id'),
        fk('supersedes_id application_version_id', 'decisions.id decisions.application_version_id'),
        sa.UniqueConstraint('id', 'application_version_id'), sa.UniqueConstraint('id', 'application_id'),
        sa.UniqueConstraint('id', 'application_id', 'application_version_number'),
        enum('kind', 'RECOMMENDATION FINAL'),
        ck('kind_status', "(kind = 'RECOMMENDATION' AND status IN ('APPROVAL_CANDIDATE','REJECTION_CANDIDATE','MANUAL_REVIEW','PENDING_DATA')) OR "
           "(kind = 'FINAL' AND status IN ('MANUAL_REVIEW','PENDING_DATA','APPROVED','REJECTED'))"),
        ck('human_final_credit_decision', "status NOT IN ('APPROVED','REJECTED') OR actor_id IS NOT NULL"),
        ck('no_self_supersede', 'supersedes_id IS NULL OR supersedes_id <> id'))


class Explanation(Base):
    __table__ = table('explanations', uid('prediction_id', 'predictions.id'), col('explainer_version'),
        col('explained_output', nullable=True), col('reference_version', nullable=True), col('base_value', sa.Double, nullable=True),
        js('contributions_json'), col('remainder_value', sa.Double, nullable=True), col('additivity_error', sa.Double, nullable=True),
        col('status'), sa.UniqueConstraint('prediction_id', 'explainer_version'),
        enum('explained_output', 'raw_margin uncalibrated_probability'), enum('status', 'PENDING SUCCEEDED FAILED'),
        ck('success_requires_values', "status <> 'SUCCEEDED' OR (explained_output IS NOT NULL AND reference_version IS NOT NULL AND base_value IS NOT NULL AND remainder_value IS NOT NULL AND additivity_error IS NOT NULL)"),
        *[ck(n + '_finite', f"{n} > '-Infinity'::float8 AND {n} < 'Infinity'::float8")
          for n in ('base_value', 'remainder_value', 'additivity_error')])


class SegmentAssignment(Base):
    __table__ = table('segment_assignments', uid('prediction_id', 'predictions.id'), col('segmenter_version'),
        col('segment_id', sa.Integer, nullable=True), col('label', nullable=True), col('distance', sa.Double, nullable=True), col('status'),
        sa.UniqueConstraint('prediction_id', 'segmenter_version'), positive('distance', zero=True),
        ck('assignment_requires_values', "status <> 'ASSIGNED' OR (segment_id IS NOT NULL AND label IS NOT NULL AND distance IS NOT NULL)"),
        ck('segment_id_nonnegative', 'segment_id >= 0'), enum('status', 'ASSIGNED UNSUPPORTED'))


class Report(Base):
    __table__ = table('reports', uid('requested_by', 'users.id'), uid('application_id', 'loan_applications.id', nullable=True),
        col('report_type'), col('format'), js('filter_snapshot_json'), col('status', server_default='QUEUED'),
        col('object_key', nullable=True), col('content_hash', sa.String(64), nullable=True),
        stamp('expires_at', nullable=True), stamp('completed_at', nullable=True),
        enum('format', 'PDF XLSX'), enum('status', 'QUEUED RUNNING SUCCEEDED FAILED EXPIRED'),
        ck('completed_report_object', "status <> 'SUCCEEDED' OR (object_key IS NOT NULL AND content_hash IS NOT NULL AND completed_at IS NOT NULL)"),
        sa.Index('ix_reports_requester_created', 'requested_by', 'created_at'))


class ApplicationHistory(Base):
    __table__ = table('application_history', uid('application_id', 'loan_applications.id'),
        uid('application_version_id', nullable=True), uid('actor_id', 'users.id', nullable=True),
        col('event_type'), col('old_status', nullable=True), col('new_status', nullable=True),
        uid('decision_id', nullable=True), col('request_id'), js('redacted_event_json'),
        fk('application_version_id application_id', 'application_versions.id application_versions.application_id'),
        fk('decision_id application_version_id', 'decisions.id decisions.application_version_id'),
        ck('decision_requires_version', 'decision_id IS NULL OR application_version_id IS NOT NULL'),
        sa.Index('ix_history_application_created', 'application_id', 'created_at'))


class LoanOutcome(Base):
    __table__ = table('loan_outcomes', uid('application_id', 'loan_applications.id'), col('outcome_definition_version'),
        stamp('observation_end'), col('outcome_matured', sa.Boolean, server_default=sa.false()),
        col('default_observed', sa.Boolean, nullable=True), col('exposure', money, nullable=True),
        col('loss_amount', money, nullable=True), uid('source_snapshot_id', nullable=True),
        fk('source_snapshot_id application_id', 'source_snapshots.id source_snapshots.application_id'),
        ck('matured_outcome', '(outcome_matured AND default_observed IS NOT NULL) OR (NOT outcome_matured AND default_observed IS NULL)'),
        positive('exposure', zero=True), positive('loss_amount', zero=True))


class AuditEvent(Base):
    __table__ = table('audit_events', uid('actor_id', 'users.id', nullable=True), col('action'),
        col('entity_type'), uid('entity_id'), col('request_id'), js('redacted_metadata_json'),
        sa.Index('ix_audit_auth_rate', 'action', 'entity_id', 'created_at'))


class OutboxEvent(Base):
    __table__ = table('outbox_events', uid('aggregate_id'), col('event_type'), col('payload_reference'),
        stamp('dispatched_at', nullable=True), col('attempt_count', sa.Integer, server_default='0'),
        ck('attempt_nonnegative', 'attempt_count >= 0'),
        sa.Index('ix_outbox_pending_created', 'created_at', postgresql_where=sa.text('dispatched_at IS NULL')))


# Every hash field stores a SHA-256 hex digest, never an unbounded placeholder.
for t in Base.metadata.tables.values():
    for c in t.columns:
        if isinstance(c.type, sa.String) and c.type.length == 64:
            t.append_constraint(ck(c.name + '_sha256', f"{c.name} ~ '^[0-9a-f]{{64}}$'"))
