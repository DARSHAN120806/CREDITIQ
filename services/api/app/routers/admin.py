from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from app.auth.dependencies import require_role
from app.db.session import get_session
from app.db.models import User, LoanApplication, Prediction
from app.schemas.auth import UserView
from app.schemas.applications import ApplicationView, ApplicationPage
from app.services.users import user_view
from app.services import applications as service
from app.services.model_research import load_dashboard

router = APIRouter(prefix='/api/v1/admin', tags=['admin-read-only'], dependencies=[Depends(require_role('ADMIN'))])


@router.get('/users')
def users(limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0), db: Session = Depends(get_session)):
    rows = db.scalars(select(User).order_by(User.created_at.desc(), User.id).limit(limit).offset(offset)).all()
    return dict(items=[user_view(db, row) for row in rows], total=db.scalar(select(func.count()).select_from(User)),
                limit=limit, offset=offset, mode='RESEARCH_ONLY', release_ready=False)


@router.get('/users/{id}', response_model=UserView)
def user(id: UUID, db: Session = Depends(get_session)):
    row = db.get(User, id)
    if row is None:
        raise HTTPException(404, 'User not found')
    return user_view(db, row)


@router.get('/applications', response_model=ApplicationPage)
def applications(limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0), db: Session = Depends(get_session)):
    return service.list_applications(db, None, limit, offset)


@router.get('/applications/{id}', response_model=ApplicationView)
def application(id: UUID, db: Session = Depends(get_session)):
    return service.application_view(db, service.owned(db, id), True)


@router.get('/statistics')
def statistics(db: Session = Depends(get_session)):
    return dict(total_users=db.scalar(select(func.count()).select_from(User)),
        total_applications=db.scalar(select(func.count()).select_from(LoanApplication)),
        total_predictions=db.scalar(select(func.count()).select_from(Prediction)), mode='RESEARCH_ONLY', release_ready=False)


@router.get('/model-research')
def model_research():
    return load_dashboard()
