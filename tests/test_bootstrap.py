from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.core.security import verify_password
from app.models.audit_log import AuditLog
from app.models.enums import AuditAction, Role
from app.models.refresh_token import RefreshToken
from app.models.tenant import Tenant
from app.models.user import User
from app.services.bootstrap import BootstrapAdminPayload, BootstrapConflictError, BootstrapService


def build_payload(*, password: str = "StrongPass123!", rotate_password: bool = False):
    return BootstrapAdminPayload(
        tenant_name="Platform",
        tenant_slug="platform",
        full_name="System Admin",
        email="admin@platform.example",
        password=password,
        rotate_password=rotate_password,
    )


def test_bootstrap_service_creates_system_admin_and_tenant(db_session) -> None:
    result = BootstrapService(db_session).ensure_system_admin(build_payload())

    assert result.tenant_created is True
    assert result.user_created is True
    assert result.password_rotated is False

    tenant = db_session.scalar(select(Tenant).where(Tenant.slug == "platform"))
    user = db_session.scalar(select(User).where(User.email == "admin@platform.example"))
    audit_logs = list(db_session.scalars(select(AuditLog)).all())

    assert tenant is not None
    assert tenant.is_active is True
    assert user is not None
    assert user.role == Role.SYS_ADMIN
    assert user.is_active is True
    assert verify_password("StrongPass123!", user.password_hash) is True
    assert {log.action for log in audit_logs} == {
        AuditAction.TENANT_CREATED,
        AuditAction.USER_CREATED,
    }


def test_bootstrap_service_is_idempotent_without_rotating_password(db_session) -> None:
    service = BootstrapService(db_session)

    initial_result = service.ensure_system_admin(build_payload(password="StrongPass123!"))
    repeated_result = service.ensure_system_admin(build_payload(password="AnotherPass123!"))

    tenant_count = len(list(db_session.scalars(select(Tenant)).all()))
    user_count = len(list(db_session.scalars(select(User)).all()))
    user = db_session.scalar(select(User).where(User.email == "admin@platform.example"))

    assert initial_result.user_created is True
    assert repeated_result.tenant_created is False
    assert repeated_result.user_created is False
    assert repeated_result.password_rotated is False
    assert tenant_count == 1
    assert user_count == 1
    assert user is not None
    assert verify_password("StrongPass123!", user.password_hash) is True


def test_bootstrap_service_can_reset_password_and_unlock_existing_admin(db_session) -> None:
    tenant = Tenant(name="Platform", slug="platform", is_active=False)
    user = User(
        tenant=tenant,
        email="admin@platform.example",
        full_name="Old Admin",
        password_hash="$2b$12$ZqL84c3Y6H7xkYH7xkYH7u4u6xTiFqouBZfyqCkCmZJLdnOjFkW3a",
        role=Role.SYS_ADMIN,
        is_active=False,
        failed_login_attempts=5,
        locked_until=datetime.now(UTC) + timedelta(minutes=15),
    )
    refresh_token = RefreshToken(
        user=user,
        token_hash="existing-refresh-hash",
        expires_at=datetime.now(UTC) + timedelta(days=7),
    )
    db_session.add_all([tenant, user, refresh_token])
    db_session.commit()

    result = BootstrapService(db_session).ensure_system_admin(
        build_payload(password="RecoveredPass123!", rotate_password=True)
    )

    db_session.expire_all()
    refreshed_tenant = db_session.scalar(select(Tenant).where(Tenant.slug == "platform"))
    refreshed_user = db_session.scalar(select(User).where(User.email == "admin@platform.example"))
    refreshed_token = db_session.scalar(select(RefreshToken).where(RefreshToken.user_id == user.id))

    assert result.tenant_created is False
    assert result.user_created is False
    assert result.password_rotated is True
    assert refreshed_tenant is not None
    assert refreshed_tenant.is_active is True
    assert refreshed_user is not None
    assert refreshed_user.is_active is True
    assert refreshed_user.failed_login_attempts == 0
    assert refreshed_user.locked_until is None
    assert verify_password("RecoveredPass123!", refreshed_user.password_hash) is True
    assert refreshed_token is not None
    assert refreshed_token.revoked_at is not None


def test_bootstrap_service_rejects_non_system_admin_conflict(db_session) -> None:
    tenant = Tenant(name="Platform", slug="platform", is_active=True)
    user = User(
        tenant=tenant,
        email="admin@platform.example",
        full_name="Platform User",
        password_hash="irrelevant",
        role=Role.USER,
        is_active=True,
    )
    db_session.add_all([tenant, user])
    db_session.commit()

    with pytest.raises(BootstrapConflictError, match="not a system administrator"):
        BootstrapService(db_session).ensure_system_admin(build_payload())
