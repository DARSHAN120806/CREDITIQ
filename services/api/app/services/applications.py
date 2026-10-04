"""Atomic synchronous research submissions using the existing immutable schema."""
from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP
import hashlib
import json
import uuid

from fastapi import HTTPException
from sqlalchemy import select, func
from sqlalchemy.dialects.postgresql import insert

from app.auth.security import utcnow
from app.db import models as M
from app.services.auth import lock_user
from app.services.lite_model import RUN_ID, RUN, ML_ROOT, digest
from app.schemas.applications import ApplicationView, ResultView


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False).encode()).hexdigest()


def owned(db, identity, user_id=None):
    query = select(M.LoanApplication).where(M.LoanApplication.id == identity)
    if user_id is not None:
        query = query.where(M.LoanApplication.user_id == user_id)
    row = db.scalar(query)
    if row is None:
        raise HTTPException(404, 'Application not found')
    return row


def result_view(db, app):
    row = db.execute(select(M.Prediction, M.RiskScore, M.Decision, M.ModelVersion)
        .join(M.RiskScore, M.RiskScore.prediction_id == M.Prediction.id)
        .join(M.Decision, M.Decision.prediction_id == M.Prediction.id)
        .join(M.ModelVersion, M.ModelVersion.id == M.Prediction.model_version_id)
        .where(M.Decision.id == app.current_decision_id)).one_or_none()
    if row is None:
        raise HTTPException(404, 'Prediction not available')
    p, r, d, m = row
    return ResultView(prediction_id=p.id, probability=p.calibrated_pd, risk_score=r.risk_score,
        risk_band=r.risk_band, credit_health_index=r.credit_health_index, recommendation=d.status,
        model_version=m.release_name, scored_at=p.scored_at, quality_flags=p.quality_flags_json)


def application_view(db, app, detail=False):
    values = dict(id=app.id, user_id=app.user_id, requested_amount=app.requested_amount,
        currency=app.currency, status=app.workflow_status, created_at=app.created_at, version=app.current_version)
    if detail:
        v = db.scalar(select(M.ApplicationVersion).where(M.ApplicationVersion.application_id == app.id,
                      M.ApplicationVersion.version == app.current_version))
        q = db.scalar(select(M.LoanQuote).where(M.LoanQuote.application_version_id == v.id))
        values.update(input=v.immutable_input_json,
            quote={'monthly_payment': str(q.monthly_payment), 'annual_rate': str(q.annual_rate),
                   'term_months': q.term_months, 'illustrative': True, 'currency': 'XXX'},
            result=result_view(db, app))
    return ApplicationView(**values)


def list_applications(db, user_id, limit, offset):
    query = select(M.LoanApplication)
    if user_id is not None:
        query = query.where(M.LoanApplication.user_id == user_id)
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    rows = db.scalars(query.order_by(M.LoanApplication.created_at.desc(), M.LoanApplication.id)
                      .limit(limit).offset(offset)).all()
    return dict(items=[application_view(db, row) for row in rows], total=total, limit=limit, offset=offset)


def register_release(db, lite):
    m = lite.metadata
    mid = uuid.uuid5(uuid.NAMESPACE_URL, 'creditiq:model:' + RUN_ID)
    pid = uuid.uuid5(uuid.NAMESPACE_URL, 'creditiq:policy:' + RUN_ID + ':sandbox-v1')
    db.execute(insert(M.ModelVersion).values(id=mid, release_name=RUN_ID, variant='LITE',
        feature_schema_version='lite-v1', target_definition_version=m['target_definition_version'],
        training_manifest_key=str(RUN / 'metadata.json'), artifact_key=str(RUN / 'best_model.joblib'),
        sha256=m['artifact_sha256']['best_model.joblib'], calibration_version=m['calibration_method'],
        runtime_lock_hash=digest(ML_ROOT / 'requirements-lock.txt'), metrics_json=m['test_metrics'],
        mode='RESEARCH_ONLY', release_ready=False).on_conflict_do_nothing(index_elements=['release_name']))
    registered = db.scalar(select(M.ModelVersion).where(M.ModelVersion.release_name == RUN_ID))
    if (registered.id != mid or registered.sha256 != m['artifact_sha256']['best_model.joblib']
            or registered.release_ready or registered.feature_schema_version != 'lite-v1'):
        raise RuntimeError('Registered model does not match pinned artifact')
    db.execute(insert(M.PolicyVersion).values(id=pid, version=RUN_ID + ':sandbox-v1',
        product_code='CASH_INSTALLMENT_V1', variant='LITE', mode='SANDBOX', approve_below=.05,
        reject_at=.15, band_thresholds_json={'low_below': .05, 'high_at': .15},
        affordability_rules_json={'evaluated': False}, effective_from=utcnow())
        .on_conflict_do_nothing(index_elements=['version']))
    policy = db.get(M.PolicyVersion, pid)
    if policy is None or policy.mode != 'SANDBOX' or policy.approve_below != .05 or policy.reject_at != .15:
        raise RuntimeError('Registered research policy mismatch')
    return mid, pid


def submit(db, principal, body, key, lite):
    request = body.model_dump(mode='json')
    body_hash = fingerprint(request)
    identity = uuid.uuid5(principal.user.id, str(key))
    try:
        # Serialize retries for a user and recheck account/session before business writes.
        user = lock_user(db, principal.user.id)
        session = db.get(M.AuthSession, principal.session.id, populate_existing=True)
        if user.account_status != 'ACTIVE' or session.revoked_at or session.expires_at <= utcnow():
            raise HTTPException(401, 'Authentication required')
        existing = db.get(M.LoanApplication, identity)
        if existing:
            version = db.scalar(select(M.ApplicationVersion).where(M.ApplicationVersion.application_id == identity))
            if version.input_hash != body_hash:
                raise HTTPException(409, 'Idempotency key already used for another payload')
            response = application_view(db, existing, True)
            db.rollback()
            return response
        now = utcnow()
        mid, pid = register_release(db, lite)
        app = M.LoanApplication(id=identity, user_id=user.id, currency='XXX',
            requested_amount=body.requested_amount, workflow_status='PROCESSING', submitted_at=now)
        db.add(app); db.flush()
        v = M.ApplicationVersion(application_id=app.id, version=1, input_schema_version='lite-submission-v1',
            immutable_input_json=request, input_hash=body_hash, as_of=now, created_by=user.id)
        db.add(v); db.flush()
        # Explicit research-only illustrative amortization, not a bank offer.
        monthly_rate = Decimal('0.12') / 12
        payment = (body.requested_amount * monthly_rate / (1 - (1 + monthly_rate) ** -body.term_months)).quantize(Decimal('.01'), rounding=ROUND_HALF_UP)
        quote = M.LoanQuote(application_version_id=v.id, product_version='illustrative-12pct-v1',
            principal=body.requested_amount, term_months=body.term_months, annual_rate=Decimal('.12'),
            monthly_payment=payment, fees_json={'illustrative': True, 'fees': 0}, currency='XXX',
            expires_at=now + timedelta(hours=1))
        db.add(quote); db.flush()
        payload = {**request, 'application_id': str(app.id), 'application_version': 1, 'as_of': now.isoformat(),
            'product_code': 'CASH_INSTALLMENT_V1', 'currency': 'XXX', 'quote_id': str(quote.id),
            'quoted_monthly_payment': str(payment)}
        quote_context = {**payload, 'expires_at': quote.expires_at.isoformat()}
        result, features = lite.score(payload, quote_context)
        feature = M.FeatureSnapshot(application_version_id=v.id, variant='LITE', feature_schema_version='lite-v1',
            feature_values_json=features, ordered_feature_hash=fingerprint(list(features.items())),
            quality_flags_json=result['data_quality_flags'], as_of=now)
        db.add(feature); db.flush()
        job = M.ScoringJob(application_version_id=v.id, variant_requested='LITE', status='SUCCEEDED',
            model_version_id=mid, idempotency_key=str(key), request_body_hash=body_hash, attempts=1, completed_at=utcnow())
        db.add(job); db.flush()
        prediction = M.Prediction(scoring_job_id=job.id, application_version_id=v.id, feature_snapshot_id=feature.id,
            model_version_id=mid, variant='LITE', raw_positive_output=result['raw_positive_output'],
            calibrated_pd=result['calibrated_pd'], quality_flags_json=result['data_quality_flags'],
            verification_status='UNVERIFIED', scored_at=utcnow())
        db.add(prediction); db.flush()
        db.add(M.RiskScore(prediction_id=prediction.id, score_policy_version='sandbox-v1',
            risk_score=result['risk_score'], risk_band=result['risk_band'], credit_health_index=result['credit_health_index']))
        decision = M.Decision(application_version_id=v.id, application_id=app.id, application_version_number=1,
            prediction_id=prediction.id, policy_version_id=pid, kind='RECOMMENDATION', status=result['recommendation'],
            reason_codes_json=['RESEARCH_ONLY', 'SELF_REPORTED_INPUT', *result['data_quality_flags']],
            affordability_snapshot_json={'evaluated': False})
        db.add(decision); db.flush()
        app.workflow_status = 'DECIDED'
        app.current_decision_id = decision.id
        db.add(M.ApplicationHistory(application_id=app.id, application_version_id=v.id, actor_id=user.id,
            event_type='RESEARCH_SCORED', old_status='PROCESSING', new_status='DECIDED', decision_id=decision.id,
            request_id=str(key), redacted_event_json={'model_version': RUN_ID, 'recommendation': decision.status}))
        db.add(M.AuditEvent(actor_id=user.id, action='RESEARCH_APPLICATION_SCORED', entity_type='application',
            entity_id=app.id, request_id=str(key), redacted_metadata_json={'mode': 'RESEARCH_ONLY'}))
        db.flush()
        response = application_view(db, app, True)
        db.commit()
        return response
    except Exception:
        db.rollback()
        raise
