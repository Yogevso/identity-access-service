from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_principal, require_roles
from app.core.principal import CurrentPrincipal
from app.db.session import get_db_session
from app.models.enums import Role
from app.schemas.rbac import (
    PrincipalResponse,
    SystemAdminSummaryResponse,
    TenantAdminSummaryResponse,
)
from app.services.rbac import (
    build_principal_response,
    build_system_admin_summary,
    build_tenant_admin_summary,
)

router = APIRouter(tags=["Authorization"])

PrincipalDep = Annotated[CurrentPrincipal, Depends(get_current_principal)]
TenantAdminDep = Annotated[
    CurrentPrincipal,
    Depends(require_roles(Role.TENANT_ADMIN, Role.SYS_ADMIN)),
]
SystemAdminDep = Annotated[CurrentPrincipal, Depends(require_roles(Role.SYS_ADMIN))]
DbSessionDep = Annotated[Session, Depends(get_db_session)]


@router.get("/auth/me", response_model=PrincipalResponse)
def read_current_principal(principal: PrincipalDep) -> PrincipalResponse:
    return build_principal_response(principal)


@router.get("/admin/tenant/summary", response_model=TenantAdminSummaryResponse)
def read_tenant_admin_summary(
    principal: TenantAdminDep,
    db: DbSessionDep,
) -> TenantAdminSummaryResponse:
    return build_tenant_admin_summary(db, principal=principal)


@router.get("/admin/system/summary", response_model=SystemAdminSummaryResponse)
def read_system_admin_summary(
    _: SystemAdminDep,
    db: DbSessionDep,
) -> SystemAdminSummaryResponse:
    return build_system_admin_summary(db)
