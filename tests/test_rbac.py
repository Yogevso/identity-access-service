from __future__ import annotations

from sqlalchemy import select

from app.models.enums import Role
from app.models.user import User
from tests.helpers import assert_api_error


def auth_headers(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}"}


def test_auth_me_requires_bearer_token(client) -> None:
    response = client.get("/api/v1/auth/me")

    assert_api_error(
        response,
        status_code=401,
        code="unauthorized",
        message="Authentication credentials were not provided or are invalid.",
    )
    assert response.headers["www-authenticate"] == "Bearer"


def test_auth_me_returns_current_principal(client, identity_factory) -> None:
    identity = identity_factory(
        role=Role.USER,
        tenant_slug="blue-sky",
        tenant_name="Blue Sky",
        email="member@bluesky.io",
        full_name="Blue Sky Member",
    )

    response = client.get("/api/v1/auth/me", headers=auth_headers(identity.access_token))

    assert response.status_code == 200
    assert response.json() == {
        "id": str(identity.user_id),
        "email": "member@bluesky.io",
        "full_name": "Blue Sky Member",
        "role": "USER",
        "tenant": {
            "id": str(identity.tenant_id),
            "name": "Blue Sky",
            "slug": "blue-sky",
        },
    }


def test_user_cannot_access_tenant_admin_summary(client, identity_factory) -> None:
    identity = identity_factory(role=Role.USER)

    response = client.get(
        "/api/v1/admin/tenant/summary",
        headers=auth_headers(identity.access_token),
    )

    assert_api_error(
        response,
        status_code=403,
        code="forbidden",
        message="You do not have permission to perform this action.",
    )


def test_tenant_admin_cannot_access_system_admin_summary(client, identity_factory) -> None:
    identity = identity_factory(role=Role.TENANT_ADMIN)

    response = client.get(
        "/api/v1/admin/system/summary",
        headers=auth_headers(identity.access_token),
    )

    assert_api_error(
        response,
        status_code=403,
        code="forbidden",
        message="You do not have permission to perform this action.",
    )


def test_tenant_admin_summary_is_scoped_to_current_tenant(client, identity_factory) -> None:
    tenant_admin = identity_factory(
        role=Role.TENANT_ADMIN,
        tenant_slug="acme",
        tenant_name="Acme",
    )
    identity_factory(role=Role.USER, tenant_slug="acme", tenant_name="Acme")
    identity_factory(role=Role.USER, tenant_slug="globex", tenant_name="Globex")

    response = client.get(
        "/api/v1/admin/tenant/summary",
        headers=auth_headers(tenant_admin.access_token),
    )

    assert response.status_code == 200
    assert response.json() == {
        "tenant_id": str(tenant_admin.tenant_id),
        "tenant_name": "Acme",
        "tenant_slug": "acme",
        "total_users": 2,
        "active_users": 2,
        "tenant_admins": 1,
        "standard_users": 1,
    }


def test_sys_admin_can_access_system_admin_summary_across_tenants(client, identity_factory) -> None:
    sys_admin = identity_factory(
        role=Role.SYS_ADMIN,
        tenant_slug="platform",
        tenant_name="Platform",
        email="sysadmin@platform.io",
    )
    identity_factory(role=Role.TENANT_ADMIN, tenant_slug="acme", tenant_name="Acme")
    identity_factory(role=Role.USER, tenant_slug="acme", tenant_name="Acme")
    identity_factory(role=Role.USER, tenant_slug="globex", tenant_name="Globex")

    response = client.get(
        "/api/v1/admin/system/summary",
        headers=auth_headers(sys_admin.access_token),
    )

    assert response.status_code == 200
    assert response.json() == {
        "total_tenants": 3,
        "active_tenants": 3,
        "total_users": 4,
        "system_admins": 1,
        "tenant_admins": 1,
        "standard_users": 2,
    }


def test_old_access_token_is_rejected_after_role_change(
    client,
    db_session,
    identity_factory,
) -> None:
    identity = identity_factory(role=Role.SYS_ADMIN)

    user = db_session.scalar(select(User).where(User.id == identity.user_id))
    assert user is not None
    user.role = Role.USER
    db_session.commit()

    response = client.get(
        "/api/v1/admin/system/summary",
        headers=auth_headers(identity.access_token),
    )

    assert_api_error(
        response,
        status_code=401,
        code="unauthorized",
        message="Authentication credentials were not provided or are invalid.",
    )
