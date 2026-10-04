from uuid import UUID
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import Principal, current_principal, require_csrf, require_role
from app.db.session import get_session
from app.db.models import ApplicationHistory
from app.schemas.applications import ApplicationRequest, ApplicationView, ApplicationPage, ResultView, HistoryView
from app.services import applications as service

router = APIRouter(prefix='/api/v1/applications', tags=['applications'])


@router.post('', response_model=ApplicationView, status_code=201, dependencies=[Depends(require_csrf)])
def create(body: ApplicationRequest, request: Request, idempotency_key: UUID = Header(),
           principal: Principal = Depends(require_role('USER')), db: Session = Depends(get_session)):
    lite = request.app.state.lite_model
    if lite is None:
        raise HTTPException(503, 'Research model unavailable')
    return service.submit(db, principal, body, idempotency_key, lite)


@router.get('', response_model=ApplicationPage)
def listing(limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0),
            principal: Principal = Depends(current_principal), db: Session = Depends(get_session)):
    return service.list_applications(db, principal.user.id, limit, offset)


@router.get('/{id}', response_model=ApplicationView)
def detail(id: UUID, principal: Principal = Depends(current_principal), db: Session = Depends(get_session)):
    return service.application_view(db, service.owned(db, id, principal.user.id), True)


@router.get('/{id}/result', response_model=ResultView)
def result(id: UUID, principal: Principal = Depends(current_principal), db: Session = Depends(get_session)):
    return service.result_view(db, service.owned(db, id, principal.user.id))


@router.get('/{id}/history', response_model=list[HistoryView])
def history(id: UUID, principal: Principal = Depends(current_principal), db: Session = Depends(get_session)):
    service.owned(db, id, principal.user.id)
    rows = db.scalars(select(ApplicationHistory).where(ApplicationHistory.application_id == id)
                      .order_by(ApplicationHistory.created_at, ApplicationHistory.id)).all()
    return [HistoryView(id=r.id, event_type=r.event_type, created_at=r.created_at, details=r.redacted_event_json) for r in rows]
