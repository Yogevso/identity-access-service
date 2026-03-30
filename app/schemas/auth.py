from __future__ import annotations

import uuid
from typing import Annotated

from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints, field_validator

from app.models.enums import Role

TenantSlug = Annotated[
    str,
    StringConstraints(
        min_length=3,
        max_length=80,
        pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
    ),
]
TenantName = Annotated[str, StringConstraints(min_length=3, max_length=120)]
FullName = Annotated[str, StringConstraints(min_length=2, max_length=120)]
Password = Annotated[str, StringConstraints(min_length=8, max_length=128)]


class RegisterRequest(BaseModel):
    tenant_name: TenantName
    tenant_slug: TenantSlug
    full_name: FullName
    email: EmailStr
    password: Password

    @field_validator("tenant_name", "full_name", mode="before")
    @classmethod
    def strip_human_names(cls, value: str) -> str:
        return value.strip()

    @field_validator("tenant_slug", mode="before")
    @classmethod
    def normalize_tenant_slug(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()


class LoginRequest(BaseModel):
    tenant_slug: TenantSlug
    email: EmailStr
    password: Password

    @field_validator("tenant_slug", mode="before")
    @classmethod
    def normalize_tenant_slug(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()


class RefreshTokenRequest(BaseModel):
    refresh_token: Annotated[str, StringConstraints(min_length=20, max_length=512)]


class LogoutRequest(BaseModel):
    refresh_token: Annotated[str, StringConstraints(min_length=20, max_length=512)]


class AuthTenantResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str


class AuthUserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    email: EmailStr
    full_name: str
    role: Role
    is_active: bool


class AuthTokensResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = Field(default="bearer")
    access_token_expires_in: int = Field(ge=1)
    user: AuthUserResponse
    tenant: AuthTenantResponse
