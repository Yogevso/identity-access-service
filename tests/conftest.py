from __future__ import annotations

import uuid
from collections.abc import Generator
from dataclasses import dataclass

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.security import create_access_token, hash_password
from app.db.base import Base
from app.main import create_application
from app.models.enums import Role
from app.models.tenant import Tenant
from app.models.user import User


@dataclass(slots=True)
class SeededIdentity:
    user_id: uuid.UUID
    tenant_id: uuid.UUID
    tenant_name: str
    tenant_slug: str
    email: str
    full_name: str
    role: Role
    access_token: str


@pytest.fixture()
def client() -> Generator[TestClient, None, None]:
    settings = Settings(
        APP_NAME="Identity Access Service Test",
        APP_ENV="test",
        APP_VERSION="0.1.0-test",
        API_V1_PREFIX="/api/v1",
        DATABASE_URL="sqlite+pysqlite:///:memory:",
        JWT_SECRET_KEY="test-secret-key",
    )
    app = create_application(settings)
    Base.metadata.create_all(bind=app.state.engine)

    with TestClient(app) as test_client:
        yield test_client

    Base.metadata.drop_all(bind=app.state.engine)


@pytest.fixture()
def db_session(client: TestClient) -> Generator[Session, None, None]:
    with client.app.state.session_factory() as session:
        yield session


@pytest.fixture()
def identity_factory(client: TestClient):
    def factory(
        *,
        role: Role = Role.USER,
        tenant_slug: str = "acme",
        tenant_name: str = "Acme",
        email: str | None = None,
        full_name: str = "Test User",
        password: str = "StrongPass123!",
        tenant_active: bool = True,
        user_active: bool = True,
    ) -> SeededIdentity:
        with client.app.state.session_factory() as session:
            tenant = session.scalar(select(Tenant).where(Tenant.slug == tenant_slug))
            if tenant is None:
                tenant = Tenant(
                    name=tenant_name,
                    slug=tenant_slug,
                    is_active=tenant_active,
                )
                session.add(tenant)
                session.flush()
            else:
                tenant.is_active = tenant_active

            user = User(
                tenant=tenant,
                email=email or f"{role.value.lower()}-{uuid.uuid4().hex[:8]}@example.com",
                full_name=full_name,
                password_hash=hash_password(password),
                role=role,
                is_active=user_active,
            )
            session.add(user)
            session.commit()
            session.refresh(user)
            session.refresh(tenant)

            return SeededIdentity(
                user_id=user.id,
                tenant_id=tenant.id,
                tenant_name=tenant.name,
                tenant_slug=tenant.slug,
                email=user.email,
                full_name=user.full_name,
                role=user.role,
                access_token=create_access_token(user=user, settings=client.app.state.settings),
            )

    return factory
