"""Transactional, immutable history imports with ownership and replay protection."""
import hashlib
import json
from uuid import uuid4
from fastapi import HTTPException
from sqlalchemy import select, func
from app.db import models as M
from app.schemas.installments import AnalysisView
from app.services.auth import lock_user
from app.services.installment_metrics import calculate, VERSION


def view(source, analysis):
    return AnalysisView(id=analysis.id, import_id=source.id, created_at=analysis.created_at,
        calculation_version=analysis.calculation_version, label=source.label, source_kind=source.source_kind,
        currency=source.currency, as_of=source.as_of, window_start=source.window_start, **analysis.result_json)


def lookup(db, identity, user_id=None, by_import=False):
    query = select(M.InstallmentImport, M.InstallmentAnalysis).join(M.InstallmentAnalysis,
        M.InstallmentAnalysis.import_id == M.InstallmentImport.id).where(
        (M.InstallmentImport.id if by_import else M.InstallmentAnalysis.id) == identity)
    if user_id is not None:
        query = query.where(M.InstallmentImport.user_id == user_id)
    row = db.execute(query).one_or_none()
    if row is None:
        raise HTTPException(404, 'Installment analysis not found')
    return view(*row)


def import_history(db, principal, body, key):
    content = body.model_dump(mode='json')
    fingerprint = hashlib.sha256(json.dumps(content, sort_keys=True, allow_nan=False).encode()).hexdigest()
    lock_user(db, principal.user.id)  # serializes identical/concurrent imports for this owner
    old = db.scalar(select(M.InstallmentImport).where(M.InstallmentImport.user_id == principal.user.id,
                                                     M.InstallmentImport.idempotency_key == str(key)))
    if old:
        if old.content_hash != fingerprint:
            raise HTTPException(409, 'Idempotency key already used for different history')
        return lookup(db, old.id, principal.user.id, by_import=True)
    result = calculate(body)
    source = M.InstallmentImport(id=uuid4(), user_id=principal.user.id, idempotency_key=str(key),
        content_hash=fingerprint, label=body.label, source_kind=body.source_kind, currency=body.currency,
        as_of=body.as_of, window_start=body.window_start, coverage_json=result['coverage'])
    db.add(source); db.flush()
    keys = {}
    for s in body.schedules:
        schedule = M.InstallmentSchedule(id=uuid4(), import_id=source.id, **s.model_dump())
        keys[(s.account_ref,s.installment_ref)] = schedule.id
        db.add(schedule)
    db.flush()
    for p in body.payments:
        db.add(M.InstallmentPayment(import_id=source.id, schedule_id=keys[(p.account_ref,p.installment_ref)],
            event_ref=p.event_ref, paid_date=p.paid_date, amount=p.amount))
    analysis = M.InstallmentAnalysis(import_id=source.id, calculation_version=VERSION, result_json=result)
    db.add(analysis)
    db.add(M.AuditEvent(actor_id=principal.user.id, action='INSTALLMENT_HISTORY_ANALYZED',
        entity_type='installment_import', entity_id=source.id, request_id=str(key),
        redacted_metadata_json={'calculation_version':VERSION, 'source_kind':body.source_kind}))
    db.flush()
    response = view(source, analysis)  # validate before committing any records
    db.commit()
    return response


def listing(db, user_id, limit, offset):
    condition = [] if user_id is None else [M.InstallmentImport.user_id == user_id]
    total = db.scalar(select(func.count()).select_from(M.InstallmentAnalysis)
        .join(M.InstallmentImport).where(*condition))
    rows = db.execute(select(M.InstallmentImport, M.InstallmentAnalysis)
        .join(M.InstallmentAnalysis, M.InstallmentAnalysis.import_id == M.InstallmentImport.id)
        .where(*condition).order_by(M.InstallmentAnalysis.created_at.desc(),M.InstallmentAnalysis.id)
        .limit(limit).offset(offset)).all()
    return dict(items=[view(*row) for row in rows], total=total, limit=limit, offset=offset)


def statistics(db):
    # Aggregate in PostgreSQL; demo scores are not pooled with personal history.
    total = db.scalar(select(func.count()).select_from(M.InstallmentImport))
    demo = db.scalar(select(func.count()).select_from(M.InstallmentImport).where(M.InstallmentImport.source_kind=='DEMO'))
    score = M.InstallmentAnalysis.result_json['metrics']['discipline_score'].as_float()
    avg, scored = db.execute(select(func.avg(score),func.count(score)).join(M.InstallmentImport,
        M.InstallmentImport.id == M.InstallmentAnalysis.import_id).where(M.InstallmentImport.source_kind=='USER_DECLARED')).one()
    return dict(total_analyses=total, demonstration_analyses=demo, personal_analyses=total-demo,
                scored_personal_analyses=scored, average_discipline_score=round(avg,2) if avg is not None else None)
