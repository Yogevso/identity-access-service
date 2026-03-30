from __future__ import annotations

import uuid
from typing import Annotated

from pydantic import BaseModel, ConfigDict, EmailStr, StringConstraints, field_validator

from app.models.enums import Role

FullName = Annotated[str, StringConstraints(min_length=2, max_length=120)]
Password = Annotated[str, StringConstraints(min_length=8, max_length=128)]


class UserCreateRequest(BaseModel):
    email: EmailStr
    full_name: FullName
    password: Password
    role: Role = Role.USER
    is_active: bool = True

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("full_name", mode="before")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return value.strip()


class UserRoleUpdateRequest(BaseModel):
    role: Role


class ManagedUserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    email: EmailStr
    full_name: str
    role: Role
    is_active: bool
