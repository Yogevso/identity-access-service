from __future__ import annotations

from sqlalchemy import select

from app.models.audit_log import AuditLog
from app.models.enums import AuditAction
from app.models.refresh_token import RefreshToken
from app.models.tenant import Tenant
from app.models.user import User


def build_register_payload() -> dict[str, str]:
    return {
        "tenant_name": "Acme Incorporated",
        "tenant_slug": "acme-inc",
        "full_name": "Alice Admin",
        "email": "admin@acmeapp.io",
        "password": "StrongPass123!",
    }


def db_rows(
    client,
    model: type[User] | type[Tenant] | type[RefreshToken] | type[AuditLog],
) -> list[User] | list[Tenant] | list[RefreshToken] | list[AuditLog]:
    with client.app.state.session_factory() as session:
        return list(session.scalars(select(model)).all())


def test_register_creates_tenant_admin_session_and_audit_trail(client) -> None:
    response = client.post("/api/v1/auth/register", json=build_register_payload())

    assert response.status_code == 201

    payload = response.json()
    assert payload["token_type"] == "bearer"
    assert payload["user"]["role"] == "TENANT_ADMIN"
    assert payload["tenant"]["slug"] == "acme-inc"
    assert payload["refresh_token"].count(".") == 1

    users = db_rows(client, User)
    tenants = db_rows(client, Tenant)
    refresh_tokens = db_rows(client, RefreshToken)
    audit_logs = db_rows(client, AuditLog)

    assert len(users) == 1
    assert len(tenants) == 1
    assert len(refresh_tokens) == 1
    assert {log.action for log in audit_logs} == {
        AuditAction.TENANT_CREATED,
        AuditAction.USER_CREATED,
    }

    _, refresh_secret = payload["refresh_token"].split(".", maxsplit=1)
    assert refresh_tokens[0].token_hash != refresh_secret
    assert len(refresh_tokens[0].token_hash) == 64


def test_register_rejects_duplicate_tenant_slug(client) -> None:
    payload = build_register_payload()

    first_response = client.post("/api/v1/auth/register", json=payload)
    second_response = client.post("/api/v1/auth/register", json=payload)

    assert first_response.status_code == 201
    assert second_response.status_code == 409
    assert second_response.json()["detail"] == "Tenant slug already exists."


def test_login_rejects_invalid_credentials(client) -> None:
    client.post("/api/v1/auth/register", json=build_register_payload())

    response = client.post(
        "/api/v1/auth/login",
        json={
            "tenant_slug": "acme-inc",
            "email": "admin@acmeapp.io",
            "password": "WrongPass123!",
        },
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid tenant, email, or password."


def test_refresh_rotates_refresh_tokens(client) -> None:
    register_response = client.post("/api/v1/auth/register", json=build_register_payload())
    original_refresh_token = register_response.json()["refresh_token"]

    refresh_response = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": original_refresh_token},
    )

    assert refresh_response.status_code == 200

    refreshed_payload = refresh_response.json()
    assert refreshed_payload["refresh_token"] != original_refresh_token

    replay_response = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": original_refresh_token},
    )

    assert replay_response.status_code == 401
    assert replay_response.json()["detail"] == "Refresh token is invalid."

    refresh_tokens = db_rows(client, RefreshToken)
    assert len(refresh_tokens) == 2
    assert sum(token.revoked_at is not None for token in refresh_tokens) == 1


def test_logout_revokes_refresh_token(client) -> None:
    register_response = client.post("/api/v1/auth/register", json=build_register_payload())
    refresh_token = register_response.json()["refresh_token"]

    logout_response = client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": refresh_token},
    )
    refresh_response = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )

    assert logout_response.status_code == 204
    assert refresh_response.status_code == 401
    assert refresh_response.json()["detail"] == "Refresh token is invalid."
