from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_principal, require_roles
from app.core.principal import CurrentPrincipal
from app.db.session import get_db_session
from app.models.enums import AuditAction, Role
from app.schemas.audit import AuditLogListResponse
from app.services.audit import AuditService
from app.services.tenants import TenantAccessDeniedError, TenantNotFoundError

router = APIRouter(tags=["Audit"])

PrincipalDep = Annotated[CurrentPrincipal, Depends(get_current_principal)]
SystemAdminDep = Annotated[CurrentPrincipal, Depends(require_roles(Role.SYS_ADMIN))]
DbSessionDep = Annotated[Session, Depends(get_db_session)]
ActionQuery = Annotated[AuditAction | None, Query()]
ActorIdQuery = Annotated[uuid.UUID | None, Query()]
TenantIdQuery = Annotated[uuid.UUID | None, Query()]
LimitQuery = Annotated[int, Query(ge=1, le=100)]
OffsetQuery = Annotated[int, Query(ge=0)]


@router.get("/audit-logs", response_model=AuditLogListResponse)
def list_system_audit_logs(
    _: SystemAdminDep,
    db: DbSessionDep,
    action: ActionQuery = None,
    tenant_id: TenantIdQuery = None,
    actor_user_id: ActorIdQuery = None,
    limit: LimitQuery = 50,
    offset: OffsetQuery = 0,
) -> AuditLogListResponse:
    service = AuditService(db)
    return service.list_system_audit_logs(
        action=action,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        limit=limit,
        offset=offset,
    )


@router.get("/tenants/{tenant_id}/audit-logs", response_model=AuditLogListResponse)
def list_tenant_audit_logs(
    tenant_id: uuid.UUID,
    principal: PrincipalDep,
    db: DbSessionDep,
    action: ActionQuery = None,
    actor_user_id: ActorIdQuery = None,
    limit: LimitQuery = 50,
    offset: OffsetQuery = 0,
) -> AuditLogListResponse:
    service = AuditService(db)
    try:
        return service.list_tenant_audit_logs(
            principal=principal,
            tenant_id=tenant_id,
            action=action,
            actor_user_id=actor_user_id,
            limit=limit,
            offset=offset,
        )
    except TenantNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except TenantAccessDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
