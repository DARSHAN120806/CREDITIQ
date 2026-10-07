"""Real PostgreSQL tests. Destructive round trips are confined to the named test DB."""
from datetime import datetime, timedelta, timezone
import os
import uuid

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext

from app.core.config import Settings
from app.db import models as M
from app.db.base import Base
from scripts.local_db import owner_url, migration_config

HASH = 'a' * 64
NOW = datetime.now(timezone.utc)


def test_migration_verification_snapshot_is_repeatable(engine):
    from scripts.database_snapshot import snapshot

    with engine.connect() as connection:
        first = snapshot(connection)
    with engine.connect() as connection:
        second = snapshot(connection)
    assert first == second
    assert first['revision'] == '20261003_0003'
    assert set(first['tables']) == set(Base.metadata.tables)
    assert all(len(value['sha256']) == 64 and value['rows'] >= 0
               for value in first['tables'].values())


@pytest.fixture(scope='module')
def engine():
    if os.environ.get('CREDITIQ_TEST_POSTGRES') != '1':
        pytest.skip('Set CREDITIQ_TEST_POSTGRES=1 after starting the isolated test cluster')
    url = owner_url('creditiq_migration_test')
    assert url.host == '127.0.0.1' and url.port == 55432 and url.database == 'creditiq_migration_test'
    engine = sa.create_engine(url, connect_args={'connect_timeout': 5})
    with engine.begin() as c:
        assert c.scalar(sa.text('SELECT current_database()')) == 'creditiq_migration_test'
        command.upgrade(migration_config(c), 'head')
    yield engine
    engine.dispose()


@pytest.fixture
def db(engine):
    with engine.connect() as c:
        tx = c.begin()
        yield c
        tx.rollback()


def insert(db, model, **values):
    return db.execute(sa.insert(model.__table__).values(**values).returning(model.__table__.c.id)).scalar_one()


def applicant(db):
    user = insert(db, M.User, normalized_email=f'{uuid.uuid4()}@example.test', password_hash='test-only-hash')
    app = insert(db, M.LoanApplication, user_id=user, currency='XXX', requested_amount=1000)
    ver = insert(db, M.ApplicationVersion, application_id=app, version=1,
                 input_schema_version='lite-v1', input_hash=HASH, as_of=NOW, created_by=user)
    return user, app, ver


def prediction_input(db):
    user, app, ver = applicant(db)
    model = insert(db, M.ModelVersion, release_name=str(uuid.uuid4()), variant='LITE', feature_schema_version='lite-v1',
                   target_definition_version='research', training_manifest_key='manifest', artifact_key='artifact',
                   sha256=HASH, calibration_version='sigmoid', runtime_lock_hash=HASH)
    feature = insert(db, M.FeatureSnapshot, application_version_id=ver, variant='LITE',
                     feature_schema_version='lite-v1', ordered_feature_hash=HASH, as_of=NOW)
    job = insert(db, M.ScoringJob, application_version_id=ver, model_version_id=model,
                 idempotency_key='test', request_body_hash=HASH)
    values = dict(scoring_job_id=job, application_version_id=ver, model_version_id=model,
                  feature_snapshot_id=feature, variant='LITE', raw_positive_output=0.5,
                  calibrated_pd=0.1, verification_status='UNVERIFIED', scored_at=NOW)
    return (user, app, ver), values


def reject(db, callback, code='23514'):
    with pytest.raises(sa.exc.DBAPIError) as error:
        with db.begin_nested():
            callback()
            db.execute(sa.text('SET CONSTRAINTS ALL IMMEDIATE'))
    assert error.value.orig.sqlstate == code


def test_upgrade_downgrade_reupgrade_and_no_schema_drift(engine):
    with engine.begin() as c:
        assert c.scalar(sa.text('SELECT current_database()')) == 'creditiq_migration_test'
        command.downgrade(migration_config(c), 'base')
        assert set(sa.inspect(c).get_table_names()) <= {'alembic_version'}
        assert c.scalar(sa.text("SELECT count(*) FROM pg_proc WHERE proname LIKE 'creditiq_%'")) == 0
        command.upgrade(migration_config(c), 'head')
        command.upgrade(migration_config(c), 'head')  # repeated upgrade is a no-op
        assert set(sa.inspect(c).get_table_names()) == set(Base.metadata.tables) | {'alembic_version'}
        assert c.scalar(sa.text('SELECT version_num FROM alembic_version')) == '20261003_0003'
        assert compare_metadata(MigrationContext.configure(c, opts={'compare_type': True}), Base.metadata) == []
        triggers = c.scalar(sa.text("SELECT count(*) FROM pg_trigger WHERE tgname='immutable_record' AND NOT tgisinternal"))
        assert triggers == 18


@pytest.mark.parametrize('value', [-0.01, 1.01, float('nan'), float('inf'), float('-inf')])
def test_pd_requires_finite_unit_interval(db, value):
    _, values = prediction_input(db)
    reject(db, lambda: insert(db, M.Prediction, **{**values, 'calibrated_pd': value}))


@pytest.mark.parametrize('value', [0, -1, 'NaN', 'Infinity'])
def test_money_requires_positive_finite_amount(db, value):
    _, _, ver = applicant(db)
    reject(db, lambda: insert(db, M.LoanQuote, application_version_id=ver, product_version='v1',
                             principal=value, term_months=12, annual_rate=0.05, monthly_payment=90,
                             currency='XXX', expires_at=NOW + timedelta(days=1)),
           '22003' if value == 'Infinity' else '23514')


@pytest.mark.parametrize('a,r', [(0.2, 0.1), (None, 0.1), (0.1, None), (0, 0.1), (0.1, float('nan'))])
def test_threshold_pair_and_order(db, a, r):
    reject(db, lambda: insert(db, M.PolicyVersion, version=str(uuid.uuid4()), product_code='CASH_INSTALLMENT_V1',
                             variant='LITE', approve_below=a, reject_at=r, effective_from=NOW))


def test_research_gates(db):
    _, values = prediction_input(db)
    # Existing model records cannot be promoted or otherwise overwritten.
    reject(db, lambda: db.execute(sa.update(M.ModelVersion).values(release_ready=True)))
    reject(db, lambda: insert(db, M.PolicyVersion, version='live', product_code='CASH_INSTALLMENT_V1',
                             variant='FULL', mode='LIVE', effective_from=NOW))
    record = db.execute(sa.select(M.ModelVersion.mode, M.ModelVersion.release_ready)).one()
    assert record == ('RESEARCH_ONLY', False)
    original = dict(db.execute(sa.select(M.ModelVersion.__table__)).mappings().one())
    original.pop('id'); original.pop('created_at')
    for invalid in ({'release_ready': True}, {'mode': 'LIVE'}):
        reject(db, lambda invalid=invalid: insert(db, M.ModelVersion,
               **{**original, 'release_name': str(uuid.uuid4()), **invalid}))


def test_cross_application_prediction_and_source_provenance(db):
    _, values = prediction_input(db)
    _, app2, ver2 = applicant(db)
    reject(db, lambda: insert(db, M.Prediction, **{**values, 'application_version_id': ver2}), '23503')
    source = insert(db, M.SourceSnapshot, application_version_id=ver2, application_id=app2,
                    source_type='bureau', state='CONFIRMED_EMPTY', source_as_of=NOW,
                    fetched_at=NOW, schema_version='v1')
    reject(db, lambda: db.execute(sa.insert(M.FeatureSnapshotSource).values(
        feature_snapshot_id=values['feature_snapshot_id'], source_snapshot_id=source,
        application_version_id=values['application_version_id'])), '23503')


def test_cross_owner_consent_and_duplicate_idempotency(db):
    (owner1, app1, ver1), values = prediction_input(db)
    owner2, _, ver2 = applicant(db)
    reject(db, lambda: insert(db, M.DataConsent, application_id=app1, user_id=owner2,
                             purpose='test', source_scope='bureau', consent_version='v1', granted_at=NOW), '23503')
    reject(db, lambda: insert(db, M.ScoringJob, application_version_id=ver1, idempotency_key='test', request_body_hash=HASH), '23505')
    insert(db, M.ScoringJob, application_version_id=ver2, idempotency_key='test', request_body_hash=HASH)


def test_current_decision_must_match_current_application_revision(db):
    (user, app, ver), values = prediction_input(db)
    pred = insert(db, M.Prediction, **values)
    _, app2, _ = applicant(db)
    policy = insert(db, M.PolicyVersion, version='sandbox', product_code='CASH_INSTALLMENT_V1',
                    variant='LITE', effective_from=NOW)
    decision = insert(db, M.Decision, application_version_id=ver, application_id=app,
                      application_version_number=1, prediction_id=pred, policy_version_id=policy,
                      kind='FINAL', status='MANUAL_REVIEW')
    reject(db, lambda: db.execute(sa.update(M.LoanApplication).where(M.LoanApplication.id==app2).values(current_decision_id=decision)), '23503')
    db.execute(sa.update(M.LoanApplication).where(M.LoanApplication.id==app).values(current_decision_id=decision))
    db.execute(sa.text('SET CONSTRAINTS ALL IMMEDIATE'))
    insert(db, M.ApplicationVersion, application_id=app, version=2,
           input_schema_version='lite-v1', input_hash=HASH, as_of=NOW, created_by=user)
    # Version 2 exists: rejection must be due to the stale current decision.
    reject(db, lambda: db.execute(sa.update(M.LoanApplication).where(M.LoanApplication.id==app).values(current_version=2)), '23503')


@pytest.mark.parametrize('operation', ['update', 'delete'])
def test_predictions_and_versions_are_immutable(db, operation):
    (_, _, ver), values = prediction_input(db)
    pred = insert(db, M.Prediction, **values)
    for model, ident, changes in [(M.Prediction, pred, {'calibrated_pd':0.2}),
                                   (M.ApplicationVersion, ver, {'input_hash':'b'*64})]:
        stmt = sa.update(model).values(**changes) if operation=='update' else sa.delete(model)
        reject(db, lambda stmt=stmt, model=model, ident=ident: db.execute(stmt.where(model.id==ident)))


def test_partial_unique_active_deployment(db):
    _, values = prediction_input(db)
    data = dict(product_code='CASH_INSTALLMENT_V1', variant='LITE', model_version_id=values['model_version_id'], activated_at=NOW)
    first = insert(db, M.ModelDeployment, **data)
    reject(db, lambda: insert(db, M.ModelDeployment, **data), '23505')
    db.execute(sa.update(M.ModelDeployment).where(M.ModelDeployment.id==first).values(retired_at=NOW))
    insert(db, M.ModelDeployment, **data)


def test_outcome_maturity_and_json_shape(db):
    _, app, _ = applicant(db)
    reject(db, lambda: insert(db, M.LoanOutcome, application_id=app, outcome_definition_version='v1',
                             observation_end=NOW, outcome_matured=False, default_observed=False))
    reject(db, lambda: insert(db, M.AuditEvent, action='test', entity_type='application', entity_id=app,
                             request_id='test', redacted_metadata_json=[]))


def test_transaction_rollback_is_atomic(engine):
    with engine.connect() as c:
        tx=c.begin()
        _, app, _=applicant(c)
        tx.rollback()
        assert c.scalar(sa.select(sa.func.count()).select_from(M.LoanApplication).where(M.LoanApplication.id==app))==0


def test_configured_application_role_connects_but_cannot_create_or_truncate(engine):
    settings=Settings()
    assert settings.pg_database == 'creditiq' and settings.pg_port == 55432
    runtime=sa.create_engine(settings.database_url)
    try:
        with runtime.connect() as c:
            assert c.scalar(sa.text('SELECT current_user')) == 'creditiq_app'
            assert c.scalar(sa.text("SELECT rolsuper FROM pg_roles WHERE rolname=current_user")) is False
            # Development may contain real accounts. Check access, never its emptiness,
            # and inspect denied privileges without attempting destructive SQL there.
            assert c.scalar(sa.text('SELECT count(*) FROM users')) >= 0
            assert c.scalar(sa.text("SELECT has_schema_privilege(current_user, 'public', 'CREATE')")) is False
            assert c.scalar(sa.text("SELECT has_table_privilege(current_user, 'users', 'TRUNCATE')")) is False
    finally:
        runtime.dispose()

