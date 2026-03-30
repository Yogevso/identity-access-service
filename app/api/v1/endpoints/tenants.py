from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_principal, require_roles
from app.core.principal import CurrentPrincipal
from app.db.session import get_db_session
from app.models.enums import Role
from app.schemas.tenants import (
    TenantCreateRequest,
    TenantResponse,
    TenantUpdateRequest,
    TenantUserSummaryResponse,
)
from app.services.tenants import (
    TenantAccessDeniedError,
    TenantConflictError,
    TenantNotFoundError,
    TenantService,
)

router = APIRouter(prefix="/tenants", tags=["Tenants"])

PrincipalDep = Annotated[CurrentPrincipal, Depends(get_current_principal)]
SystemAdminDep = Annotated[CurrentPrincipal, Depends(require_roles(Role.SYS_ADMIN))]
DbSessionDep = Annotated[Session, Depends(get_db_session)]


@router.get("", response_model=list[TenantResponse])
def list_tenants(
    _: SystemAdminDep,
    db: DbSessionDep,
) -> list[TenantResponse]:
    service = TenantService(db)
    return service.list_tenants()


@router.post("", response_model=TenantResponse, status_code=status.HTTP_201_CREATED)
def create_tenant(
    payload: TenantCreateRequest,
    request: Request,
    principal: SystemAdminDep,
    db: DbSessionDep,
) -> TenantResponse:
    service = TenantService(db)
    try:
        return service.create_tenant(
            payload,
            actor=principal,
            ip_address=request.client.host if request.client is not None else None,
            user_agent=request.headers.get("user-agent"),
        )
    except TenantConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.get("/me", response_model=TenantResponse)
def read_current_tenant(
    principal: PrincipalDep,
    db: DbSessionDep,
) -> TenantResponse:
    service = TenantService(db)
    return service.get_current_tenant(principal)


@router.get("/{tenant_id}", response_model=TenantResponse)
def read_tenant(
    tenant_id: uuid.UUID,
    principal: PrincipalDep,
    db: DbSessionDep,
) -> TenantResponse:
    service = TenantService(db)
    try:
        return service.get_tenant(principal=principal, tenant_id=tenant_id)
    except TenantNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.patch("/{tenant_id}", response_model=TenantResponse)
def update_tenant(
    tenant_id: uuid.UUID,
    payload: TenantUpdateRequest,
    principal: PrincipalDep,
    db: DbSessionDep,
) -> TenantResponse:
    service = TenantService(db)
    try:
        return service.update_tenant(tenant_id, payload, principal=principal)
    except TenantNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except TenantAccessDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc


@router.get("/{tenant_id}/users", response_model=list[TenantUserSummaryResponse])
def list_tenant_users(
    tenant_id: uuid.UUID,
    principal: PrincipalDep,
    db: DbSessionDep,
) -> list[TenantUserSummaryResponse]:
    service = TenantService(db)
    try:
        return service.list_tenant_users(principal=principal, tenant_id=tenant_id)
    except TenantNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except TenantAccessDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
