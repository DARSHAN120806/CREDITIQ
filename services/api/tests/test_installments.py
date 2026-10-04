import uuid
from concurrent.futures import ThreadPoolExecutor
import pytest
from sqlalchemy import select, func, update, text
from sqlalchemy.orm import Session
from app.db import models as M
from app.services import installments as service
from test_authentication import api, owner_engine, signed_in, register, login
from test_installment_metrics import history


def send(client,body=None,key=None):
    token=client.get('/api/v1/auth/csrf').json()['csrf_token']
    return client.post('/api/v1/installment-history/imports',json=body or history(),
        headers={'X-CSRF-Token':token,'Idempotency-Key':str(key or uuid.uuid4())})


def test_import_atomic_storage_replay_and_timeline(api):
    client,_,engine=api;signed_in(client);key=uuid.uuid4()
    response=send(client,key=key)
    assert response.status_code==201,response.text
    a=response.json()
    assert a['metrics']['late_payment_count']==1
    assert send(client,key=key).json()['id']==a['id']
    assert send(client,{**history(),'label':'Different'},key).status_code==409
    assert client.get('/api/v1/installment-analyses').json()['total']==1
    assert client.get('/api/v1/installment-analyses/'+a['id']).json()==a
    assert client.get('/api/v1/installment-history/imports/'+a['import_id']).status_code==200
    assert client.get('/api/v1/installment-analyses/'+a['id']+'/timeline').json()['timeline']==a['timeline']
    token=client.get('/api/v1/auth/csrf').json()['csrf_token']
    assert client.post('/api/v1/installment-analyses',json={'import_id':a['import_id']},headers={'X-CSRF-Token':token}).json()==a
    with Session(engine) as db:
        for model,count in ((M.InstallmentImport,1),(M.InstallmentSchedule,2),(M.InstallmentPayment,2),(M.InstallmentAnalysis,1),(M.Prediction,0)):
            assert db.scalar(select(func.count()).select_from(model))==count


def test_ownership_read_only_admin_and_statistics(api):
    client,_,engine=api;signed_in(client);a=send(client).json()
    register(client,email='other@example.com');login(client,email='other@example.com')
    assert client.get('/api/v1/installment-analyses').json()['total']==0
    for path in ('/installment-analyses/'+a['id'],'/installment-analyses/'+a['id']+'/timeline','/installment-history/imports/'+a['import_id']):
        assert client.get('/api/v1'+path).status_code==404
    assert client.get('/api/v1/admin/installment-statistics').status_code==403
    with engine.begin() as c:c.execute(update(M.User).where(M.User.normalized_email=='other@example.com').values(role='ADMIN'))
    assert send(client).status_code==403
    assert client.get('/api/v1/admin/installment-analyses').json()['total']==1
    assert client.get('/api/v1/admin/installment-analyses/'+a['id']).status_code==200
    stats=client.get('/api/v1/admin/installment-statistics').json()
    assert stats['personal_analyses']==1 and stats['average_discipline_score'] is None
    assert all(set(v)=={'get'} for k,v in client.get('/openapi.json').json()['paths'].items() if k.startswith('/api/v1/admin/'))


def test_auth_csrf_validation_and_body_bounds(api):
    client,_,_=api
    assert client.get('/api/v1/installment-analyses').status_code==401
    assert send(client).status_code==401
    signed_in(client)
    assert client.post('/api/v1/installment-history/imports',json=history()).status_code==403
    assert send(client,{**history(),'schedules':[]}).status_code==422
    token=client.get('/api/v1/auth/csrf').json()['csrf_token']
    assert client.post('/api/v1/installment-history/imports',content='x'*1048577,headers={'X-CSRF-Token':token}).status_code==413
    assert client.get('/api/v1/installment-analyses').headers['cache-control']=='no-store'


def test_failure_rolls_back_import_and_audit(api,monkeypatch):
    client,_,engine=api;signed_in(client)
    def fail(*args):raise RuntimeError('response failure')
    monkeypatch.setattr(service,'view',fail)
    with pytest.raises(RuntimeError,match='response failure'):send(client)
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(M.InstallmentImport))==0
        assert db.scalar(select(func.count()).select_from(M.AuditEvent).where(M.AuditEvent.action=='INSTALLMENT_HISTORY_ANALYZED'))==0


def test_database_immutability_and_cross_import_allocation(api):
    from sqlalchemy.exc import IntegrityError
    client,_,engine=api;signed_in(client);a=send(client).json();b=send(client,key=uuid.uuid4()).json()
    with engine.connect() as c:
        for table in ('installment_imports','installment_schedules','installment_payments','installment_analyses'):
            with pytest.raises(IntegrityError):
                with c.begin_nested():c.execute(text(f'DELETE FROM {table}'))
        schedule=c.scalar(select(M.InstallmentSchedule.id).where(M.InstallmentSchedule.import_id==uuid.UUID(a['import_id'])))
        with pytest.raises(IntegrityError):
            with c.begin_nested():c.execute(M.InstallmentPayment.__table__.insert().values(import_id=uuid.UUID(b['import_id']),schedule_id=schedule,event_ref='cross',paid_date='2026-09-01',amount=10))
        c.rollback()


def test_concurrent_import_same_key_creates_one_snapshot(api):
    from app.auth.dependencies import Principal
    from app.schemas.installments import HistoryImportRequest
    client,_,engine=api;signed_in(client)
    with Session(engine) as db:
        user=db.scalar(select(M.User));session=db.scalar(select(M.AuthSession))
        principal=Principal(user,session)
    key=uuid.uuid4()
    def worker():
        with Session(engine,expire_on_commit=False) as db:
            return service.import_history(db,principal,HistoryImportRequest.model_validate(history()),key).id
    with ThreadPoolExecutor(max_workers=2) as pool:
        values=list(pool.map(lambda _:worker(),range(2)))
    assert values[0]==values[1]
