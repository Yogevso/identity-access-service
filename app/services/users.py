from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.principal import CurrentPrincipal
from app.core.security import hash_password
from app.models.enums import AuditAction, Role
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.schemas.users import ManagedUserResponse, UserCreateRequest, UserRoleUpdateRequest
from app.services.audit import record_audit_event
from app.services.tenants import TenantService


class ManagedUserConflictError(Exception):
    """Raised when a managed user operation violates a unique or state constraint."""


class ManagedUserNotFoundError(Exception):
    """Raised when a managed user is not visible or does not exist."""


class UserManagementAccessDeniedError(Exception):
    """Raised when the caller cannot perform a user-management action."""


class UserManagementService:
    def __init__(self, db: Session):
        self.db = db
        self.tenant_service = TenantService(db)

    def list_users(
        self,
        *,
        principal: CurrentPrincipal,
        tenant_id: uuid.UUID,
    ) -> list[ManagedUserResponse]:
        tenant = self.tenant_service.resolve_visible_tenant(
            principal=principal,
            tenant_id=tenant_id,
            allowed_same_tenant_roles={Role.TENANT_ADMIN, Role.SYS_ADMIN},
        )
        users = self.db.scalars(
            select(User)
            .where(User.tenant_id == tenant.id)
            .order_by(User.email.asc())
        ).all()
        return [ManagedUserResponse.model_validate(user) for user in users]

    def create_user(
        self,
        tenant_id: uuid.UUID,
        payload: UserCreateRequest,
        *,
        actor: CurrentPrincipal,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> ManagedUserResponse:
        tenant = self.tenant_service.resolve_visible_tenant(
            principal=actor,
            tenant_id=tenant_id,
            allowed_same_tenant_roles={Role.TENANT_ADMIN, Role.SYS_ADMIN},
        )
        self._ensure_role_assignment_allowed(actor_role=actor.role, target_role=payload.role)

        existing_user = self.db.scalar(
            select(User).where(User.tenant_id == tenant.id, User.email == str(payload.email))
        )
        if existing_user is not None:
            raise ManagedUserConflictError("A user with this email already exists in the tenant.")

        user = User(
            tenant=tenant,
            email=str(payload.email),
            full_name=payload.full_name,
            password_hash=hash_password(payload.password),
            role=payload.role,
            is_active=payload.is_active,
        )
        self.db.add(user)
        self.db.flush()
        record_audit_event(
            self.db,
            action=AuditAction.USER_CREATED,
            resource_type="user",
            resource_id=str(user.id),
            tenant_id=tenant.id,
            actor_user_id=actor.user_id,
            details={"role": user.role.value, "source": "admin_api"},
            ip_address=ip_address,
            user_agent=user_agent,
        )
        self.db.commit()
        self.db.refresh(user)
        return ManagedUserResponse.model_validate(user)

    def update_user_role(
        self,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        payload: UserRoleUpdateRequest,
        *,
        actor: CurrentPrincipal,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> ManagedUserResponse:
        self.tenant_service.resolve_visible_tenant(
            principal=actor,
            tenant_id=tenant_id,
            allowed_same_tenant_roles={Role.TENANT_ADMIN, Role.SYS_ADMIN},
        )
        user = self._get_visible_user(actor=actor, tenant_id=tenant_id, user_id=user_id)
        self._ensure_manageable_target(actor_role=actor.role, target_role=user.role)
        self._ensure_role_assignment_allowed(actor_role=actor.role, target_role=payload.role)

        previous_role = user.role
        user.role = payload.role
        if previous_role != payload.role:
            record_audit_event(
                self.db,
                action=AuditAction.ROLE_CHANGED,
                resource_type="user",
                resource_id=str(user.id),
                tenant_id=user.tenant_id,
                actor_user_id=actor.user_id,
                details={"old_role": previous_role.value, "new_role": payload.role.value},
                ip_address=ip_address,
                user_agent=user_agent,
            )
        self.db.commit()
        self.db.refresh(user)
        return ManagedUserResponse.model_validate(user)

    def deactivate_user(
        self,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        *,
        actor: CurrentPrincipal,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> None:
        self.tenant_service.resolve_visible_tenant(
            principal=actor,
            tenant_id=tenant_id,
            allowed_same_tenant_roles={Role.TENANT_ADMIN, Role.SYS_ADMIN},
        )
        user = self._get_visible_user(actor=actor, tenant_id=tenant_id, user_id=user_id)
        self._ensure_manageable_target(actor_role=actor.role, target_role=user.role)

        if actor.user_id == user.id:
            raise UserManagementAccessDeniedError("You cannot deactivate your own account.")

        if not user.is_active:
            return

        user.is_active = False
        self._revoke_user_refresh_tokens(user.id)
        record_audit_event(
            self.db,
            action=AuditAction.USER_DEACTIVATED,
            resource_type="user",
            resource_id=str(user.id),
            tenant_id=user.tenant_id,
            actor_user_id=actor.user_id,
            details={"email": user.email},
            ip_address=ip_address,
            user_agent=user_agent,
        )
        self.db.commit()

    def _get_visible_user(
        self,
        *,
        actor: CurrentPrincipal,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> User:
        user = self.db.scalar(
            select(User).where(User.id == user_id, User.tenant_id == tenant_id)
        )
        if user is None:
            raise ManagedUserNotFoundError("User not found.")

        if actor.role != Role.SYS_ADMIN and actor.tenant_id != user.tenant_id:
            raise ManagedUserNotFoundError("User not found.")

        return user

    def _revoke_user_refresh_tokens(self, user_id: uuid.UUID) -> None:
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

    @staticmethod
    def _ensure_manageable_target(*, actor_role: Role, target_role: Role) -> None:
        if actor_role != Role.SYS_ADMIN and target_role == Role.SYS_ADMIN:
            raise UserManagementAccessDeniedError(
                "You do not have permission to manage system administrators."
            )

    @staticmethod
    def _ensure_role_assignment_allowed(*, actor_role: Role, target_role: Role) -> None:
        if actor_role != Role.SYS_ADMIN and target_role == Role.SYS_ADMIN:
            raise UserManagementAccessDeniedError(
                "You do not have permission to assign the system administrator role."
            )
