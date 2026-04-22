from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    plan: str
    is_active: bool
    whitelisted: bool
    is_admin: bool
    created_at: datetime


class AuthResponse(BaseModel):
    user: UserResponse | None = None
    message: str


class AdminUserResponse(BaseModel):
    """Extended user view returned by admin endpoints."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    plan: str
    is_active: bool
    whitelisted: bool
    is_admin: bool
    created_at: datetime
    updated_at: datetime


class TokenResponse(BaseModel):
    # Backward-compatible placeholder schema removed from active use.
    user: UserResponse | None = None
    message: str = ""


class AdminModelItem(BaseModel):
    id: str
    name: str
    tier: str
    provider: str = ""


class AdminModelsResponse(BaseModel):
    models: list[AdminModelItem]


class AdminModelsUpdate(BaseModel):
    models: list[str]
