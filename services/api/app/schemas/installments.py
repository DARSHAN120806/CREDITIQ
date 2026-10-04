"""Bounded user-declared effective schedules and allocated payments."""
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, model_validator

Reference = Annotated[str, Field(min_length=1, max_length=80, pattern=r'^[A-Za-z0-9_.:-]+$')]
Amount = Annotated[Decimal, Field(gt=0, le=100000000, max_digits=12, decimal_places=2)]

class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid')

class ScheduledInstallment(StrictModel):
    account_ref: Reference
    installment_ref: Reference
    schedule_version: Reference = '1'
    due_date: date
    amount: Amount

class PaymentEvent(StrictModel):
    event_ref: Reference
    account_ref: Reference
    installment_ref: Reference
    paid_date: date
    amount: Annotated[Decimal, Field(ge=0, le=100000000, max_digits=12, decimal_places=2)]

class HistoryImportRequest(StrictModel):
    label: str = Field(min_length=1, max_length=120)
    source_kind: Literal['USER_DECLARED', 'DEMO'] = 'USER_DECLARED'
    currency: Literal['INR', 'XXX'] = 'INR'
    as_of: date
    window_start: date
    schedule_complete: bool
    payments_complete: bool
    effective_schedule_confirmed: Literal[True]
    schedules: list[ScheduledInstallment] = Field(min_length=1, max_length=500)
    payments: list[PaymentEvent] = Field(max_length=2000)

    @model_validator(mode='after')
    def reconcile_input(self):
        today = datetime.now(timezone.utc).date()
        if not date(1900, 1, 1) <= self.window_start <= self.as_of <= today:
            raise ValueError('Use an observation window ending on or before today')
        if self.source_kind == 'DEMO' and self.currency != 'XXX':
            raise ValueError('Demo history uses unspecified currency XXX')
        keys = [(s.account_ref, s.installment_ref) for s in self.schedules]
        if len(set(keys)) != len(keys):
            raise ValueError('Supply one effective version per account/installment; resolve schedule conflicts first')
        if any(not date(1900, 1, 1) <= s.due_date <= date(2200, 1, 1) for s in self.schedules):
            raise ValueError('Invalid due date')
        events = {}
        keyset = set(keys)
        for p in self.payments:
            if (p.account_ref, p.installment_ref) not in keyset:
                raise ValueError('Payment references an unknown installment')
            if not date(1900, 1, 1) <= p.paid_date <= today:
                raise ValueError('Invalid payment date')
            if p.event_ref in events and events[p.event_ref] != p:
                raise ValueError('Conflicting duplicate payment event identity')
            events[p.event_ref] = p
        self.payments = list(events.values())
        return self

class AnalysisRequest(StrictModel):
    import_id: UUID

class AnalysisView(StrictModel):
    id: UUID
    import_id: UUID
    created_at: datetime
    calculation_version: str
    label: str
    source_kind: str
    currency: str
    as_of: date
    window_start: date
    metrics: dict
    coverage: dict
    timeline: list[dict]
    installments: list[dict]
    aggregates: dict

class AnalysisPage(StrictModel):
    items: list[AnalysisView]
    total: int
    limit: int
    offset: int
