from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import Principal, require_csrf, require_role
from app.db import models as M
from app.db.session import get_session
from app.schemas.planner import PlannerRequest, PlannerResponse
from app.services.borrowing_planner import calculate

router = APIRouter(prefix='/api/v1/planner', tags=['borrowing planner'])


@router.post('/plan', response_model=PlannerResponse, dependencies=[Depends(require_csrf)])
def create_plan(body: PlannerRequest, principal: Principal = Depends(require_role('USER')),
                db: Session = Depends(get_session)):
    if body.application_id is not None:
        exists = db.scalar(select(M.LoanApplication.id).where(
            M.LoanApplication.id == body.application_id,
            M.LoanApplication.user_id == principal.user.id))
        if exists is None:
            raise HTTPException(404, 'Application not found')
    # Pure arithmetic only: this endpoint does not access the model or write records.
    return calculate(body)
