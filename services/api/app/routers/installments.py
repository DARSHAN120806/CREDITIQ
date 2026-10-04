from uuid import UUID
from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy.orm import Session
from app.auth.dependencies import Principal, current_principal, require_csrf, require_role
from app.db.session import get_session
from app.schemas.installments import HistoryImportRequest, AnalysisRequest, AnalysisView, AnalysisPage
from app.services import installments as service

router = APIRouter(prefix='/api/v1', tags=['installment intelligence'])

@router.post('/installment-history/imports', response_model=AnalysisView, status_code=201, dependencies=[Depends(require_csrf)])
def create(body: HistoryImportRequest, idempotency_key: UUID = Header(),
           principal: Principal = Depends(require_role('USER')), db: Session = Depends(get_session)):
    return service.import_history(db, principal, body, idempotency_key)

@router.get('/installment-history/imports/{id}', response_model=AnalysisView)
def imported(id: UUID, principal: Principal = Depends(current_principal), db: Session = Depends(get_session)):
    return service.lookup(db, id, principal.user.id, by_import=True)

@router.post('/installment-analyses', response_model=AnalysisView, dependencies=[Depends(require_csrf)])
def analyze(body: AnalysisRequest, principal: Principal = Depends(require_role('USER')), db: Session = Depends(get_session)):
    # V1 imports atomically calculate their one immutable analysis. Replays return that snapshot.
    return service.lookup(db, body.import_id, principal.user.id, by_import=True)

@router.get('/installment-analyses', response_model=AnalysisPage)
def listing(limit: int = Query(10,ge=1,le=50), offset: int = Query(0,ge=0),
            principal: Principal = Depends(current_principal), db: Session = Depends(get_session)):
    return service.listing(db, principal.user.id, limit, offset)

@router.get('/installment-analyses/{id}', response_model=AnalysisView)
def detail(id: UUID, principal: Principal = Depends(current_principal), db: Session = Depends(get_session)):
    return service.lookup(db, id, principal.user.id)

@router.get('/installment-analyses/{id}/timeline')
def timeline(id: UUID, principal: Principal = Depends(current_principal), db: Session = Depends(get_session)):
    result = service.lookup(db, id, principal.user.id)
    return dict(calculation_version=result.calculation_version, as_of=result.as_of, timeline=result.timeline, coverage=result.coverage)

@router.get('/admin/installment-analyses', response_model=AnalysisPage)
def admin_list(limit: int = Query(10,ge=1,le=50), offset: int = Query(0,ge=0),
               principal: Principal = Depends(require_role('ADMIN')), db: Session = Depends(get_session)):
    return service.listing(db, None, limit, offset)

@router.get('/admin/installment-analyses/{id}', response_model=AnalysisView)
def admin_detail(id: UUID, principal: Principal = Depends(require_role('ADMIN')), db: Session = Depends(get_session)):
    return service.lookup(db, id)

@router.get('/admin/installment-statistics')
def admin_statistics(principal: Principal = Depends(require_role('ADMIN')), db: Session = Depends(get_session)):
    return service.statistics(db)
