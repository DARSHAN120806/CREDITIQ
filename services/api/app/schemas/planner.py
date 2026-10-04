"""Strict user-declared inputs for stateless borrowing calculations."""
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

Amount = Annotated[Decimal, Field(ge=0, le=1_000_000_000, max_digits=14, decimal_places=2)]
PositiveAmount = Annotated[Decimal, Field(gt=0, le=1_000_000_000, max_digits=14, decimal_places=2)]
Priority = Literal['LOWER_EMI', 'LOWER_TOTAL_INTEREST', 'BALANCED']


class PlannerRequest(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)

    currency: Literal['INR']
    application_id: UUID | None = None
    as_of: date = Field(default_factory=lambda: datetime.now(timezone.utc).date())
    monthly_take_home_income: PositiveAmount
    monthly_gross_income: PositiveAmount | None = None
    monthly_essential_expenses: Amount
    existing_monthly_debt_payments: Amount
    total_outstanding_debt: Amount | None = None
    liquid_savings: Amount | None = None
    monthly_savings_goal: Amount | None = None
    requested_amount: PositiveAmount
    annual_rate_percent: Annotated[Decimal, Field(ge=0, le=1000, max_digits=8, decimal_places=4)] = Decimal('12')
    terms_months: list[Annotated[int, Field(ge=6, le=360, strict=True)]] = Field(
        default_factory=lambda: [12, 24, 36, 48, 60], min_length=1, max_length=12)
    planning_priority: Priority = 'BALANCED'
    loan_purpose: str | None = Field(default=None, max_length=120)

    @field_validator('terms_months')
    @classmethod
    def unique_terms(cls, value: list[int]) -> list[int]:
        if len(value) != len(set(value)):
            raise ValueError('Terms must be unique')
        return value

    @field_validator('as_of')
    @classmethod
    def not_future(cls, value: date) -> date:
        if value > datetime.now(timezone.utc).date():
            raise ValueError('As-of date cannot be in the future')
        return value


class PlannerResponse(BaseModel):
    calculation_version: str
    mode: Literal['RESEARCH_ONLY'] = 'RESEARCH_ONLY'
    release_ready: Literal[False] = False
    currency: Literal['INR']
    as_of: str
    inputs_basis: Literal['USER_DECLARED'] = 'USER_DECLARED'
    current_debt_burden_monthly: str
    current_dti: float | None
    current_take_home_payment_ratio: float
    total_outstanding_debt: str | None
    liquid_savings: str | None
    monthly_essential_expenses: str
    monthly_savings_goal: str | None
    additional_emi_headroom: str | None
    additional_emi_headroom_before_savings_goal: str
    savings_buffer_months: float | None
    planning_priority: Priority
    ranking_weights: dict[str, float]
    scenarios: list[dict]
    warnings: list[str]
