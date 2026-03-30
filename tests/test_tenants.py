from __future__ import annotations

from sqlalchemy import select

from app.models.audit_log import AuditLog
from app.models.enums import AuditAction, Role


def auth_headers(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}"}


def test_sys_admin_can_create_and_list_tenants(client, db_session, identity_factory) -> None:
    sys_admin = identity_factory(
        role=Role.SYS_ADMIN,
        tenant_slug="platform",
        tenant_name="Platform",
        email="sysadmin@platform.io",
    )

    create_response = client.post(
        "/api/v1/tenants",
        headers=auth_headers(sys_admin.access_token),
        json={"name": "Globex", "slug": "globex", "is_active": True},
    )
    list_response = client.get("/api/v1/tenants", headers=auth_headers(sys_admin.access_token))

    assert create_response.status_code == 201
    assert create_response.json()["slug"] == "globex"

    assert list_response.status_code == 200
    assert [tenant["slug"] for tenant in list_response.json()] == ["globex", "platform"]

    audit_logs = db_session.scalars(select(AuditLog)).all()
    assert any(log.action == AuditAction.TENANT_CREATED for log in audit_logs)


def test_authenticated_user_can_read_current_tenant(client, identity_factory) -> None:
    user = identity_factory(
        role=Role.USER,
        tenant_slug="blue-sky",
        tenant_name="Blue Sky",
        email="member@bluesky.io",
    )

    response = client.get("/api/v1/tenants/me", headers=auth_headers(user.access_token))

    assert response.status_code == 200
    assert response.json() == {
        "id": str(user.tenant_id),
        "name": "Blue Sky",
        "slug": "blue-sky",
        "is_active": True,
    }


def test_tenant_admin_can_only_list_users_in_own_tenant(client, identity_factory) -> None:
    tenant_admin = identity_factory(
        role=Role.TENANT_ADMIN,
        tenant_slug="acme",
        tenant_name="Acme",
        email="admin@acme.io",
    )
    identity_factory(
        role=Role.USER,
        tenant_slug="acme",
        tenant_name="Acme",
        email="member@acme.io",
    )
    other_tenant_user = identity_factory(
        role=Role.USER,
        tenant_slug="globex",
        tenant_name="Globex",
        email="member@globex.io",
    )

    own_response = client.get(
        f"/api/v1/tenants/{tenant_admin.tenant_id}/users",
        headers=auth_headers(tenant_admin.access_token),
    )
    cross_tenant_response = client.get(
        f"/api/v1/tenants/{other_tenant_user.tenant_id}/users",
        headers=auth_headers(tenant_admin.access_token),
    )

    assert own_response.status_code == 200
    own_payload = own_response.json()
    assert len(own_payload) == 2
    assert [user["email"] for user in own_payload] == ["admin@acme.io", "member@acme.io"]
    assert [user["role"] for user in own_payload] == ["TENANT_ADMIN", "USER"]
    assert all(user["is_active"] is True for user in own_payload)

    assert cross_tenant_response.status_code == 404
    assert cross_tenant_response.json()["detail"] == "Tenant not found."


def test_standard_user_cannot_list_same_tenant_users(client, identity_factory) -> None:
    user = identity_factory(
        role=Role.USER,
        tenant_slug="acme",
        tenant_name="Acme",
        email="member@acme.io",
    )
    identity_factory(
        role=Role.TENANT_ADMIN,
        tenant_slug="acme",
        tenant_name="Acme",
        email="admin@acme.io",
    )

    response = client.get(
        f"/api/v1/tenants/{user.tenant_id}/users",
        headers=auth_headers(user.access_token),
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "You do not have permission to perform this action."


def test_sys_admin_can_update_any_tenant(client, identity_factory) -> None:
    sys_admin = identity_factory(
        role=Role.SYS_ADMIN,
        tenant_slug="platform",
        tenant_name="Platform",
    )
    tenant_member = identity_factory(
        role=Role.TENANT_ADMIN,
        tenant_slug="acme",
        tenant_name="Acme",
    )

    patch_response = client.patch(
        f"/api/v1/tenants/{tenant_member.tenant_id}",
        headers=auth_headers(sys_admin.access_token),
        json={"name": "Acme Updated", "is_active": False},
    )
    read_response = client.get(
        f"/api/v1/tenants/{tenant_member.tenant_id}",
        headers=auth_headers(sys_admin.access_token),
    )

    assert patch_response.status_code == 200
    assert patch_response.json() == {
        "id": str(tenant_member.tenant_id),
        "name": "Acme Updated",
        "slug": "acme",
        "is_active": False,
    }

    assert read_response.status_code == 200
    assert read_response.json()["is_active"] is False


def test_tenant_admin_cannot_update_own_tenant(client, identity_factory) -> None:
    tenant_admin = identity_factory(
        role=Role.TENANT_ADMIN,
        tenant_slug="acme",
        tenant_name="Acme",
    )

    response = client.patch(
        f"/api/v1/tenants/{tenant_admin.tenant_id}",
        headers=auth_headers(tenant_admin.access_token),
        json={"name": "Renamed Tenant"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "You do not have permission to perform this action."
