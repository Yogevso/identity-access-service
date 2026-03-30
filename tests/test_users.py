from __future__ import annotations

from sqlalchemy import select

from app.models.audit_log import AuditLog
from app.models.enums import AuditAction, Role
from app.models.refresh_token import RefreshToken
from app.models.user import User


def auth_headers(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}"}


def test_tenant_admin_can_create_user_and_emit_audit_log(
    client,
    db_session,
    identity_factory,
) -> None:
    tenant_admin = identity_factory(
        role=Role.TENANT_ADMIN,
        tenant_slug="acme",
        tenant_name="Acme",
        email="admin@acme.io",
    )

    response = client.post(
        f"/api/v1/tenants/{tenant_admin.tenant_id}/users",
        headers=auth_headers(tenant_admin.access_token),
        json={
            "email": "member@acme.io",
            "full_name": "Acme Member",
            "password": "StrongPass123!",
            "role": "USER",
            "is_active": True,
        },
    )

    assert response.status_code == 201
    assert response.json() == {
        "id": response.json()["id"],
        "tenant_id": str(tenant_admin.tenant_id),
        "email": "member@acme.io",
        "full_name": "Acme Member",
        "role": "USER",
        "is_active": True,
    }

    audit_logs = db_session.scalars(
        select(AuditLog).where(AuditLog.action == AuditAction.USER_CREATED)
    ).all()
    assert any(log.actor_user_id == tenant_admin.user_id for log in audit_logs)


def test_sys_admin_can_create_system_admin_for_any_tenant(client, identity_factory) -> None:
    sys_admin = identity_factory(
        role=Role.SYS_ADMIN,
        tenant_slug="platform",
        tenant_name="Platform",
    )
    target_tenant_admin = identity_factory(
        role=Role.TENANT_ADMIN,
        tenant_slug="globex",
        tenant_name="Globex",
    )

    response = client.post(
        f"/api/v1/tenants/{target_tenant_admin.tenant_id}/users",
        headers=auth_headers(sys_admin.access_token),
        json={
            "email": "platform-admin@globex.io",
            "full_name": "Globex Platform Admin",
            "password": "StrongPass123!",
            "role": "SYS_ADMIN",
            "is_active": True,
        },
    )

    assert response.status_code == 201
    assert response.json()["role"] == "SYS_ADMIN"
    assert response.json()["tenant_id"] == str(target_tenant_admin.tenant_id)


def test_tenant_admin_cannot_assign_system_admin_role(client, identity_factory) -> None:
    tenant_admin = identity_factory(role=Role.TENANT_ADMIN, tenant_slug="acme", tenant_name="Acme")

    response = client.post(
        f"/api/v1/tenants/{tenant_admin.tenant_id}/users",
        headers=auth_headers(tenant_admin.access_token),
        json={
            "email": "bad-idea@acme.io",
            "full_name": "Bad Idea",
            "password": "StrongPass123!",
            "role": "SYS_ADMIN",
            "is_active": True,
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"] == (
        "You do not have permission to assign the system administrator role."
    )


def test_tenant_admin_can_change_user_role_in_own_tenant(
    client,
    db_session,
    identity_factory,
) -> None:
    tenant_admin = identity_factory(role=Role.TENANT_ADMIN, tenant_slug="acme", tenant_name="Acme")
    member = identity_factory(
        role=Role.USER,
        tenant_slug="acme",
        tenant_name="Acme",
        email="member@acme.io",
    )

    response = client.patch(
        f"/api/v1/tenants/{tenant_admin.tenant_id}/users/{member.user_id}/role",
        headers=auth_headers(tenant_admin.access_token),
        json={"role": "TENANT_ADMIN"},
    )

    assert response.status_code == 200
    assert response.json()["role"] == "TENANT_ADMIN"

    audit_logs = db_session.scalars(
        select(AuditLog).where(AuditLog.action == AuditAction.ROLE_CHANGED)
    ).all()
    assert any(
        log.actor_user_id == tenant_admin.user_id
        and log.resource_id == str(member.user_id)
        for log in audit_logs
    )


def test_tenant_admin_cannot_change_cross_tenant_user_role(client, identity_factory) -> None:
    tenant_admin = identity_factory(role=Role.TENANT_ADMIN, tenant_slug="acme", tenant_name="Acme")
    foreign_user = identity_factory(role=Role.USER, tenant_slug="globex", tenant_name="Globex")

    response = client.patch(
        f"/api/v1/tenants/{foreign_user.tenant_id}/users/{foreign_user.user_id}/role",
        headers=auth_headers(tenant_admin.access_token),
        json={"role": "TENANT_ADMIN"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Tenant not found."


def test_deactivating_user_revokes_refresh_tokens_and_blocks_reauthentication(
    client,
    db_session,
    identity_factory,
) -> None:
    tenant_admin = identity_factory(
        role=Role.TENANT_ADMIN,
        tenant_slug="acme",
        tenant_name="Acme",
        email="admin@acme.io",
    )
    member = identity_factory(
        role=Role.USER,
        tenant_slug="acme",
        tenant_name="Acme",
        email="member@acme.io",
        password="StrongPass123!",
    )

    login_response = client.post(
        "/api/v1/auth/login",
        json={
            "tenant_slug": "acme",
            "email": "member@acme.io",
            "password": "StrongPass123!",
        },
    )
    assert login_response.status_code == 200
    refresh_token = login_response.json()["refresh_token"]

    deactivate_response = client.delete(
        f"/api/v1/tenants/{tenant_admin.tenant_id}/users/{member.user_id}",
        headers=auth_headers(tenant_admin.access_token),
    )
    refresh_response = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    relogin_response = client.post(
        "/api/v1/auth/login",
        json={
            "tenant_slug": "acme",
            "email": "member@acme.io",
            "password": "StrongPass123!",
        },
    )

    assert deactivate_response.status_code == 204
    assert refresh_response.status_code == 401
    assert relogin_response.status_code == 401

    refreshed_user = db_session.scalar(select(User).where(User.id == member.user_id))
    assert refreshed_user is not None
    assert refreshed_user.is_active is False

    refresh_tokens = db_session.scalars(
        select(RefreshToken).where(RefreshToken.user_id == member.user_id)
    ).all()
    assert refresh_tokens
    assert all(token.revoked_at is not None for token in refresh_tokens)


def test_tenant_admin_cannot_deactivate_own_account(client, identity_factory) -> None:
    tenant_admin = identity_factory(role=Role.TENANT_ADMIN, tenant_slug="acme", tenant_name="Acme")

    response = client.delete(
        f"/api/v1/tenants/{tenant_admin.tenant_id}/users/{tenant_admin.user_id}",
        headers=auth_headers(tenant_admin.access_token),
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "You cannot deactivate your own account."
