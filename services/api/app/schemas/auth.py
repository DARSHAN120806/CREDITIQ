from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, SecretStr, field_validator


class Credentials(BaseModel):
    model_config = ConfigDict(extra='forbid')
    email: EmailStr = Field(max_length=254)
    password: SecretStr = Field(min_length=1, max_length=128)

    @field_validator('email', mode='after')
    @classmethod
    def canonical_email(cls, value):
        return str(value).lower()


class RegisterRequest(Credentials):
    password: SecretStr = Field(min_length=15, max_length=128)
    full_name: str = Field(min_length=1, max_length=200)

    @field_validator('full_name')
    @classmethod
    def nonblank_name(cls, value):
        if not value.strip():
            raise ValueError('Name must not be blank')
        return value.strip()


class UserView(BaseModel):
    id: UUID
    email: str
    full_name: str | None
    role: str
    permissions: list[str]


class SessionView(BaseModel):
    id: UUID
    created_at: datetime
    expires_at: datetime
    current: bool


class CsrfView(BaseModel):
    csrf_token: str


class LoginView(UserView):
    csrf_token: str
    expires_in: int
