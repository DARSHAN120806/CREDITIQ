from datetime import datetime, timezone
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator, field_serializer


class ApplicationRequest(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)
    age_years: float = Field(ge=18, le=100, strict=True)
    employment_type: Literal['WORKING','COMMERCIAL_ASSOCIATE','STATE_SERVANT','PENSIONER','UNEMPLOYED','STUDENT','BUSINESSMAN','MATERNITY_LEAVE','OTHER']
    years_employed: float | None = Field(ge=0, le=100, strict=True)
    annual_income: Decimal = Field(gt=0, le=100000000, decimal_places=2)
    requested_amount: Decimal = Field(ge=1000, le=10000000, decimal_places=2)
    term_months: int = Field(ge=6, le=120, strict=True)
    education_level: Literal['LOWER_SECONDARY','SECONDARY','INCOMPLETE_HIGHER','HIGHER','ACADEMIC_DEGREE','OTHER']
    household_size: int = Field(ge=1, le=30, strict=True)
    dependent_children: int = Field(ge=0, le=29, strict=True)
    occupation: Literal['LABORER','CORE_STAFF','ACCOUNTANT','MANAGER','DRIVER','SALES','CLEANING','COOKING','PRIVATE_SERVICE','MEDICAL','SECURITY','HIGH_TECH','WAITING_BAR','LOW_SKILL_LABOR','REALTY_AGENT','SECRETARY','IT','HR','OTHER'] | None = None
    housing_status: Literal['OWN_OR_APARTMENT','WITH_PARENTS','RENTED','MUNICIPAL','OFFICE','COOPERATIVE','OTHER'] | None = None
    research_acknowledged: Literal[True]

    @model_validator(mode='after')
    def relationships(self):
        if self.years_employed is not None and self.years_employed > self.age_years:
            raise ValueError('Employment tenure cannot exceed age')
        if self.dependent_children >= self.household_size:
            raise ValueError('Children must be fewer than household members')
        return self


class ResearchResponse(BaseModel):
    mode: Literal['RESEARCH_ONLY'] = 'RESEARCH_ONLY'
    release_ready: Literal[False] = False

    @field_serializer('created_at', 'scored_at', check_fields=False)
    def utc_timestamp(self, value):
        return value.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z')


class ResultView(ResearchResponse):
    prediction_id: UUID
    probability: float
    risk_score: float
    risk_band: str
    credit_health_index: float
    recommendation: str
    decision_status: Literal['NOT_A_LENDING_DECISION'] = 'NOT_A_LENDING_DECISION'
    model_version: str
    scored_at: datetime
    quality_flags: list[str]
    currency: Literal['XXX'] = 'XXX'


class ApplicationView(ResearchResponse):
    id: UUID
    user_id: UUID
    requested_amount: Decimal
    currency: str
    status: str
    created_at: datetime
    version: int
    input: dict | None = None
    quote: dict | None = None
    result: ResultView | None = None


class ApplicationPage(ResearchResponse):
    items: list[ApplicationView]
    total: int
    limit: int
    offset: int


class HistoryView(BaseModel):
    id: UUID
    event_type: str
    created_at: datetime
    details: dict
