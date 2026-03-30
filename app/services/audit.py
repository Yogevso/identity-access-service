from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.core.principal import CurrentPrincipal
from app.models.audit_log import AuditLog
from app.models.enums import AuditAction, Role
from app.schemas.audit import (
    AuditActorResponse,
    AuditLogListResponse,
    AuditLogResponse,
    AuditTenantResponse,
)


def record_audit_event(
    db: Session,
    *,
    action: AuditAction,
    resource_type: str,
    resource_id: str,
    tenant_id: uuid.UUID | None = None,
    actor_user_id: uuid.UUID | None = None,
    details: dict[str, Any] | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> AuditLog:
    audit_log = AuditLog(
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        action=action,
        resource_type=resource_type[:64],
        resource_id=resource_id[:64],
        details=details,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    db.add(audit_log)
    return audit_log


class AuditService:
    def __init__(self, db: Session):
        from app.services.tenants import TenantService

        self.db = db
        self.tenant_service = TenantService(db)

    def list_system_audit_logs(
        self,
        *,
        action: AuditAction | None = None,
        tenant_id: uuid.UUID | None = None,
        actor_user_id: uuid.UUID | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> AuditLogListResponse:
        statement = self._build_statement(
            action=action,
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
        )
        return self._build_response(statement=statement, limit=limit, offset=offset)

    def list_tenant_audit_logs(
        self,
        *,
        principal: CurrentPrincipal,
        tenant_id: uuid.UUID,
        action: AuditAction | None = None,
        actor_user_id: uuid.UUID | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> AuditLogListResponse:
        self.tenant_service.resolve_visible_tenant(
            principal=principal,
            tenant_id=tenant_id,
            allowed_same_tenant_roles={Role.TENANT_ADMIN, Role.SYS_ADMIN},
        )
        statement = self._build_statement(
            action=action,
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
        )
        return self._build_response(statement=statement, limit=limit, offset=offset)

    def _build_statement(
        self,
        *,
        action: AuditAction | None,
        tenant_id: uuid.UUID | None,
        actor_user_id: uuid.UUID | None,
    ):
        statement = select(AuditLog).options(
            joinedload(AuditLog.tenant),
            joinedload(AuditLog.actor),
        )
        if action is not None:
            statement = statement.where(AuditLog.action == action)
        if tenant_id is not None:
            statement = statement.where(AuditLog.tenant_id == tenant_id)
        if actor_user_id is not None:
            statement = statement.where(AuditLog.actor_user_id == actor_user_id)
        return statement

    def _build_response(self, *, statement, limit: int, offset: int) -> AuditLogListResponse:
        safe_limit = min(max(limit, 1), 100)
        safe_offset = max(offset, 0)

        count_statement = select(func.count()).select_from(statement.subquery())
        total = int(self.db.scalar(count_statement) or 0)

        items = self.db.scalars(
            statement.order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
            .offset(safe_offset)
            .limit(safe_limit)
        ).all()

        return AuditLogListResponse(
            items=[self._serialize_log(audit_log) for audit_log in items],
            total=total,
            limit=safe_limit,
            offset=safe_offset,
        )

    @staticmethod
    def _serialize_log(audit_log: AuditLog) -> AuditLogResponse:
        tenant = None
        if audit_log.tenant is not None:
            tenant = AuditTenantResponse(
                id=audit_log.tenant.id,
                name=audit_log.tenant.name,
                slug=audit_log.tenant.slug,
            )

        actor = None
        if audit_log.actor is not None:
            actor = AuditActorResponse(
                id=audit_log.actor.id,
                email=audit_log.actor.email,
                full_name=audit_log.actor.full_name,
                role=audit_log.actor.role,
            )

        return AuditLogResponse(
            id=audit_log.id,
            action=audit_log.action,
            resource_type=audit_log.resource_type,
            resource_id=audit_log.resource_id,
            details=audit_log.details,
            ip_address=audit_log.ip_address,
            user_agent=audit_log.user_agent,
            created_at=audit_log.created_at,
            tenant=tenant,
            actor=actor,
        )
