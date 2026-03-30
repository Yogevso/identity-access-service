from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.enums import AuditAction, Role
from app.models.refresh_token import RefreshToken
from app.models.tenant import Tenant
from app.models.user import User
from app.services.audit import record_audit_event


class BootstrapConflictError(Exception):
    """Raised when bootstrap input conflicts with existing tenant or user state."""


@dataclass(slots=True)
class BootstrapAdminPayload:
    tenant_name: str
    tenant_slug: str
    full_name: str
    email: str
    password: str
    rotate_password: bool = False


@dataclass(slots=True)
class BootstrapAdminResult:
    tenant_id: uuid.UUID
    tenant_slug: str
    user_id: uuid.UUID
    email: str
    tenant_created: bool
    user_created: bool
    password_rotated: bool


class BootstrapService:
    def __init__(self, db: Session):
        self.db = db

    def ensure_system_admin(self, payload: BootstrapAdminPayload) -> BootstrapAdminResult:
        tenant = self.db.scalar(select(Tenant).where(Tenant.slug == payload.tenant_slug))
        tenant_created = False
        if tenant is None:
            tenant = Tenant(
                name=payload.tenant_name,
                slug=payload.tenant_slug,
                is_active=True,
            )
            self.db.add(tenant)
            self.db.flush()
            tenant_created = True
        else:
            tenant.is_active = True

        user = self.db.scalar(
            select(User).where(User.tenant_id == tenant.id, User.email == payload.email)
        )
        user_created = False
        password_rotated = False

        if user is None:
            user = User(
                tenant=tenant,
                email=payload.email,
                full_name=payload.full_name,
                password_hash=hash_password(payload.password),
                role=Role.SYS_ADMIN,
                is_active=True,
            )
            self.db.add(user)
            self.db.flush()
            user_created = True
        elif user.role != Role.SYS_ADMIN:
            raise BootstrapConflictError(
                "An existing user with this email is not a system administrator."
            )
        else:
            user.full_name = payload.full_name
            user.is_active = True
            user.failed_login_attempts = 0
            user.locked_until = None
            if payload.rotate_password:
                user.password_hash = hash_password(payload.password)
                self._revoke_active_refresh_tokens(user.id)
                password_rotated = True

        if tenant_created:
            record_audit_event(
                self.db,
                action=AuditAction.TENANT_CREATED,
                resource_type="tenant",
                resource_id=str(tenant.id),
                tenant_id=tenant.id,
                actor_user_id=user.id,
                details={"tenant_slug": tenant.slug, "source": "bootstrap_admin_cli"},
            )

        if user_created:
            record_audit_event(
                self.db,
                action=AuditAction.USER_CREATED,
                resource_type="user",
                resource_id=str(user.id),
                tenant_id=tenant.id,
                actor_user_id=user.id,
                details={"role": user.role.value, "source": "bootstrap_admin_cli"},
            )

        self.db.commit()
        self.db.refresh(tenant)
        self.db.refresh(user)
        return BootstrapAdminResult(
            tenant_id=tenant.id,
            tenant_slug=tenant.slug,
            user_id=user.id,
            email=user.email,
            tenant_created=tenant_created,
            user_created=user_created,
            password_rotated=password_rotated,
        )

    def _revoke_active_refresh_tokens(self, user_id: uuid.UUID) -> None:
        now = datetime.now(UTC)
        refresh_tokens = self.db.scalars(
            select(RefreshToken).where(
                RefreshToken.user_id == user_id,
                RefreshToken.revoked_at.is_(None),
            )
        ).all()
        for refresh_token in refresh_tokens:
            refresh_token.revoked_at = now
            refresh_token.last_used_at = now
