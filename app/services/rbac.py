from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.principal import CurrentPrincipal
from app.models.enums import Role
from app.models.tenant import Tenant
from app.models.user import User
from app.schemas.rbac import (
    PrincipalResponse,
    PrincipalTenantResponse,
    SystemAdminSummaryResponse,
    TenantAdminSummaryResponse,
)


def build_principal_response(principal: CurrentPrincipal) -> PrincipalResponse:
    return PrincipalResponse(
        id=principal.user_id,
        email=principal.email,
        full_name=principal.full_name,
        role=principal.role,
        tenant=PrincipalTenantResponse(
            id=principal.tenant_id,
            name=principal.tenant_name,
            slug=principal.tenant_slug,
        ),
    )


def build_tenant_admin_summary(
    db: Session,
    *,
    principal: CurrentPrincipal,
) -> TenantAdminSummaryResponse:
    total_users = _count_users(db, tenant_id=principal.tenant_id)
    active_users = _count_users(db, tenant_id=principal.tenant_id, is_active=True)
    tenant_admins = _count_users(db, tenant_id=principal.tenant_id, role=Role.TENANT_ADMIN)
    standard_users = _count_users(db, tenant_id=principal.tenant_id, role=Role.USER)

    return TenantAdminSummaryResponse(
        tenant_id=principal.tenant_id,
        tenant_name=principal.tenant_name,
        tenant_slug=principal.tenant_slug,
        total_users=total_users,
        active_users=active_users,
        tenant_admins=tenant_admins,
        standard_users=standard_users,
    )


def build_system_admin_summary(db: Session) -> SystemAdminSummaryResponse:
    total_tenants = _count_tenants(db)
    active_tenants = _count_tenants(db, is_active=True)
    total_users = _count_users(db)

    return SystemAdminSummaryResponse(
        total_tenants=total_tenants,
        active_tenants=active_tenants,
        total_users=total_users,
        system_admins=_count_users(db, role=Role.SYS_ADMIN),
        tenant_admins=_count_users(db, role=Role.TENANT_ADMIN),
        standard_users=_count_users(db, role=Role.USER),
    )


def _count_tenants(db: Session, *, is_active: bool | None = None) -> int:
    statement = select(func.count(Tenant.id))
    if is_active is not None:
        statement = statement.where(Tenant.is_active.is_(is_active))

    return int(db.scalar(statement) or 0)


def _count_users(
    db: Session,
    *,
    tenant_id=None,
    role: Role | None = None,
    is_active: bool | None = None,
) -> int:
    statement = select(func.count(User.id))
    if tenant_id is not None:
        statement = statement.where(User.tenant_id == tenant_id)
    if role is not None:
        statement = statement.where(User.role == role)
    if is_active is not None:
        statement = statement.where(User.is_active.is_(is_active))

    return int(db.scalar(statement) or 0)
