from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.models.enums import AuditAction, Role


class AuditActorResponse(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    role: Role


class AuditTenantResponse(BaseModel):
    id: uuid.UUID
    name: str
    slug: str


class AuditLogResponse(BaseModel):
    id: uuid.UUID
    action: AuditAction
    resource_type: str
    resource_id: str
    details: dict[str, Any] | None
    ip_address: str | None
    user_agent: str | None
    created_at: datetime
    tenant: AuditTenantResponse | None
    actor: AuditActorResponse | None


class AuditLogListResponse(BaseModel):
    items: list[AuditLogResponse]
    total: int = Field(ge=0)
    limit: int = Field(ge=1)
    offset: int = Field(ge=0)
