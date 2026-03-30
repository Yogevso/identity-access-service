from __future__ import annotations

import uuid

from pydantic import BaseModel

from app.models.enums import Role


class PrincipalTenantResponse(BaseModel):
    id: uuid.UUID
    name: str
    slug: str


class PrincipalResponse(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    role: Role
    tenant: PrincipalTenantResponse


class TenantAdminSummaryResponse(BaseModel):
    tenant_id: uuid.UUID
    tenant_name: str
    tenant_slug: str
    total_users: int
    active_users: int
    tenant_admins: int
    standard_users: int


class SystemAdminSummaryResponse(BaseModel):
    total_tenants: int
    active_tenants: int
    total_users: int
    system_admins: int
    tenant_admins: int
    standard_users: int
