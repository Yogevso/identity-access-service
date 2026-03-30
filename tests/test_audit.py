from __future__ import annotations

from app.models.enums import Role


def auth_headers(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}"}


def test_sys_admin_can_query_global_audit_logs_with_filters(client, identity_factory) -> None:
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
    tenant_id = create_response.json()["id"]

    globex_admin = identity_factory(
        role=Role.TENANT_ADMIN,
        tenant_slug="globex",
        tenant_name="Globex",
        email="admin@globex.io",
    )

    create_user_response = client.post(
        f"/api/v1/tenants/{tenant_id}/users",
        headers=auth_headers(globex_admin.access_token),
        json={
            "email": "member@globex.io",
            "full_name": "Globex Member",
            "password": "StrongPass123!",
            "role": "USER",
            "is_active": True,
        },
    )
    assert create_user_response.status_code == 201

    update_response = client.patch(
        f"/api/v1/tenants/{tenant_id}",
        headers=auth_headers(sys_admin.access_token),
        json={"name": "Globex Corporation"},
    )
    assert update_response.status_code == 200

    response = client.get(
        f"/api/v1/audit-logs?tenant_id={tenant_id}&limit=10",
        headers=auth_headers(sys_admin.access_token),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 3
    assert payload["limit"] == 10
    assert payload["offset"] == 0
    assert {item["action"] for item in payload["items"]} == {
        "TENANT_CREATED",
        "TENANT_UPDATED",
        "USER_CREATED",
    }
    assert all(item["tenant"]["slug"] == "globex" for item in payload["items"])

    filtered_response = client.get(
        f"/api/v1/audit-logs?tenant_id={tenant_id}&actor_user_id={globex_admin.user_id}",
        headers=auth_headers(sys_admin.access_token),
    )

    assert filtered_response.status_code == 200
    filtered_payload = filtered_response.json()
    assert filtered_payload["total"] == 1
    assert filtered_payload["items"][0]["action"] == "USER_CREATED"
    assert filtered_payload["items"][0]["actor"]["email"] == "admin@globex.io"


def test_tenant_admin_can_list_own_tenant_audit_logs_only(client, identity_factory) -> None:
    acme_admin = identity_factory(
        role=Role.TENANT_ADMIN,
        tenant_slug="acme",
        tenant_name="Acme",
        email="admin@acme.io",
    )
    globex_admin = identity_factory(
        role=Role.TENANT_ADMIN,
        tenant_slug="globex",
        tenant_name="Globex",
        email="admin@globex.io",
    )

    acme_create_response = client.post(
        f"/api/v1/tenants/{acme_admin.tenant_id}/users",
        headers=auth_headers(acme_admin.access_token),
        json={
            "email": "member@acme.io",
            "full_name": "Acme Member",
            "password": "StrongPass123!",
            "role": "USER",
            "is_active": True,
        },
    )
    globex_create_response = client.post(
        f"/api/v1/tenants/{globex_admin.tenant_id}/users",
        headers=auth_headers(globex_admin.access_token),
        json={
            "email": "member@globex.io",
            "full_name": "Globex Member",
            "password": "StrongPass123!",
            "role": "USER",
            "is_active": True,
        },
    )
    assert acme_create_response.status_code == 201
    assert globex_create_response.status_code == 201

    own_response = client.get(
        f"/api/v1/tenants/{acme_admin.tenant_id}/audit-logs?action=USER_CREATED",
        headers=auth_headers(acme_admin.access_token),
    )
    cross_tenant_response = client.get(
        f"/api/v1/tenants/{globex_admin.tenant_id}/audit-logs",
        headers=auth_headers(acme_admin.access_token),
    )

    assert own_response.status_code == 200
    own_payload = own_response.json()
    assert own_payload["total"] == 1
    assert own_payload["items"][0]["tenant"]["slug"] == "acme"
    assert own_payload["items"][0]["actor"]["email"] == "admin@acme.io"

    assert cross_tenant_response.status_code == 404
    assert cross_tenant_response.json()["detail"] == "Tenant not found."


def test_standard_user_cannot_list_same_tenant_audit_logs(client, identity_factory) -> None:
    user = identity_factory(
        role=Role.USER,
        tenant_slug="acme",
        tenant_name="Acme",
        email="member@acme.io",
    )

    response = client.get(
        f"/api/v1/tenants/{user.tenant_id}/audit-logs",
        headers=auth_headers(user.access_token),
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "You do not have permission to perform this action."
