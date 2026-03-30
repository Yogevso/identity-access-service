from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_principal
from app.core.principal import CurrentPrincipal
from app.db.session import get_db_session
from app.schemas.users import ManagedUserResponse, UserCreateRequest, UserRoleUpdateRequest
from app.services.tenants import TenantAccessDeniedError, TenantNotFoundError
from app.services.users import (
    ManagedUserConflictError,
    ManagedUserNotFoundError,
    UserManagementAccessDeniedError,
    UserManagementService,
)

router = APIRouter(prefix="/tenants/{tenant_id}/users", tags=["Users"])

PrincipalDep = Annotated[CurrentPrincipal, Depends(get_current_principal)]
DbSessionDep = Annotated[Session, Depends(get_db_session)]


@router.get("", response_model=list[ManagedUserResponse])
def list_users(
    tenant_id: uuid.UUID,
    principal: PrincipalDep,
    db: DbSessionDep,
) -> list[ManagedUserResponse]:
    service = UserManagementService(db)
    try:
        return service.list_users(principal=principal, tenant_id=tenant_id)
    except TenantNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except (TenantAccessDeniedError, UserManagementAccessDeniedError) as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc


@router.post("", response_model=ManagedUserResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    tenant_id: uuid.UUID,
    payload: UserCreateRequest,
    request: Request,
    principal: PrincipalDep,
    db: DbSessionDep,
) -> ManagedUserResponse:
    service = UserManagementService(db)
    try:
        return service.create_user(
            tenant_id,
            payload,
            actor=principal,
            ip_address=request.client.host if request.client is not None else None,
            user_agent=request.headers.get("user-agent"),
        )
    except TenantNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ManagedUserConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except (TenantAccessDeniedError, UserManagementAccessDeniedError) as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc


@router.patch("/{user_id}/role", response_model=ManagedUserResponse)
def update_user_role(
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    payload: UserRoleUpdateRequest,
    request: Request,
    principal: PrincipalDep,
    db: DbSessionDep,
) -> ManagedUserResponse:
    service = UserManagementService(db)
    try:
        return service.update_user_role(
            tenant_id,
            user_id,
            payload,
            actor=principal,
            ip_address=request.client.host if request.client is not None else None,
            user_agent=request.headers.get("user-agent"),
        )
    except (TenantNotFoundError, ManagedUserNotFoundError) as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except (TenantAccessDeniedError, UserManagementAccessDeniedError) as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def deactivate_user(
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    request: Request,
    principal: PrincipalDep,
    db: DbSessionDep,
) -> Response:
    service = UserManagementService(db)
    try:
        service.deactivate_user(
            tenant_id,
            user_id,
            actor=principal,
            ip_address=request.client.host if request.client is not None else None,
            user_agent=request.headers.get("user-agent"),
        )
    except (TenantNotFoundError, ManagedUserNotFoundError) as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except (TenantAccessDeniedError, UserManagementAccessDeniedError) as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    return Response(status_code=status.HTTP_204_NO_CONTENT)
