import uuid

from pydantic import BaseModel, EmailStr, Field, RootModel

from backend.core.constants import IntegrationStatus


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    full_name: str | None = None


class UserRead(BaseModel):
    id: uuid.UUID
    email: EmailStr
    full_name: str | None
    is_active: bool
    is_superuser: bool

    model_config = {"from_attributes": True}


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class IntegrationsStatus(RootModel[dict[str, IntegrationStatus]]):
    root: dict[str, IntegrationStatus]
