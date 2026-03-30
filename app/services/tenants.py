from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.principal import CurrentPrincipal
from app.models.enums import AuditAction, Role
from app.models.tenant import Tenant
from app.schemas.tenants import (
    TenantCreateRequest,
    TenantResponse,
    TenantUpdateRequest,
)
from app.services.audit import record_audit_event


class TenantConflictError(Exception):
    """Raised when a tenant unique constraint would be violated."""


class TenantNotFoundError(Exception):
    """Raised when a tenant is not visible or does not exist."""


class TenantAccessDeniedError(Exception):
    """Raised when the caller can see a tenant but cannot perform the action."""


class TenantService:
    def __init__(self, db: Session):
        self.db = db

    def list_tenants(self) -> list[TenantResponse]:
        tenants = self.db.scalars(select(Tenant).order_by(Tenant.name.asc())).all()
        return [TenantResponse.model_validate(tenant) for tenant in tenants]

    def get_current_tenant(self, principal: CurrentPrincipal) -> TenantResponse:
        tenant = self.resolve_visible_tenant(
            principal=principal,
            tenant_id=principal.tenant_id,
            allowed_same_tenant_roles={Role.USER, Role.TENANT_ADMIN, Role.SYS_ADMIN},
        )
        return TenantResponse.model_validate(tenant)

    def get_tenant(self, *, principal: CurrentPrincipal, tenant_id: uuid.UUID) -> TenantResponse:
        tenant = self.resolve_visible_tenant(
            principal=principal,
            tenant_id=tenant_id,
            allowed_same_tenant_roles={Role.USER, Role.TENANT_ADMIN, Role.SYS_ADMIN},
        )
        return TenantResponse.model_validate(tenant)

    def create_tenant(
        self,
        payload: TenantCreateRequest,
        *,
        actor: CurrentPrincipal,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> TenantResponse:
        existing_tenant = self.db.scalar(select(Tenant).where(Tenant.slug == payload.slug))
        if existing_tenant is not None:
            raise TenantConflictError("Tenant slug already exists.")

        tenant = Tenant(
            name=payload.name,
            slug=payload.slug,
            is_active=payload.is_active,
        )
        self.db.add(tenant)
        self.db.flush()
        record_audit_event(
            self.db,
            action=AuditAction.TENANT_CREATED,
            resource_type="tenant",
            resource_id=str(tenant.id),
            tenant_id=tenant.id,
            actor_user_id=actor.user_id,
            details={"tenant_slug": tenant.slug, "source": "system_admin"},
            ip_address=ip_address,
            user_agent=user_agent,
        )
        self.db.commit()
        self.db.refresh(tenant)
        return TenantResponse.model_validate(tenant)

    def update_tenant(
        self,
        tenant_id: uuid.UUID,
        payload: TenantUpdateRequest,
        *,
        principal: CurrentPrincipal,
    ) -> TenantResponse:
        tenant = self.resolve_visible_tenant(
            principal=principal,
            tenant_id=tenant_id,
            allowed_same_tenant_roles={Role.SYS_ADMIN},
        )

        updates = payload.model_dump(exclude_unset=True)
        if "name" in updates:
            tenant.name = updates["name"]
        if "is_active" in updates:
            tenant.is_active = updates["is_active"]

        self.db.commit()
        self.db.refresh(tenant)
        return TenantResponse.model_validate(tenant)

    def resolve_visible_tenant(
        self,
        *,
        principal: CurrentPrincipal,
        tenant_id: uuid.UUID,
        allowed_same_tenant_roles: set[Role],
    ) -> Tenant:
        if principal.role == Role.SYS_ADMIN:
            tenant = self.db.get(Tenant, tenant_id)
            if tenant is None:
                raise TenantNotFoundError("Tenant not found.")
            return tenant

        if principal.tenant_id != tenant_id:
            raise TenantNotFoundError("Tenant not found.")

        if principal.role not in allowed_same_tenant_roles:
            raise TenantAccessDeniedError("You do not have permission to perform this action.")

        tenant = self.db.get(Tenant, tenant_id)
        if tenant is None:
            raise TenantNotFoundError("Tenant not found.")
        return tenant
