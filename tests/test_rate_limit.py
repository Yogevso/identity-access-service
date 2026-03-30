from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.db.base import Base
from app.main import create_application
from tests.helpers import assert_api_error


@contextmanager
def build_client(**overrides) -> Generator[TestClient, None, None]:
    settings = Settings(
        APP_NAME="Identity Access Service Test",
        APP_ENV="test",
        APP_VERSION="0.1.0-test",
        API_V1_PREFIX="/api/v1",
        DATABASE_URL="sqlite+pysqlite:///:memory:",
        JWT_SECRET_KEY="test-secret-key",
        **overrides,
    )
    app = create_application(settings)
    Base.metadata.create_all(bind=app.state.engine)

    try:
        with TestClient(app) as client:
            yield client
    finally:
        Base.metadata.drop_all(bind=app.state.engine)


def test_login_rate_limit_returns_consistent_error_envelope() -> None:
    with build_client(
        LOGIN_RATE_LIMIT_REQUESTS=2,
        REGISTER_RATE_LIMIT_REQUESTS=0,
        REFRESH_RATE_LIMIT_REQUESTS=0,
        RATE_LIMIT_WINDOW_SECONDS=60,
    ) as client:
        first_response = client.post(
            "/api/v1/auth/login",
            json={
                "tenant_slug": "missing",
                "email": "admin@example.com",
                "password": "StrongPass123!",
            },
        )
        second_response = client.post(
            "/api/v1/auth/login",
            json={
                "tenant_slug": "missing",
                "email": "admin@example.com",
                "password": "StrongPass123!",
            },
        )
        limited_response = client.post(
            "/api/v1/auth/login",
            json={
                "tenant_slug": "missing",
                "email": "admin@example.com",
                "password": "StrongPass123!",
            },
        )

    assert_api_error(
        first_response,
        status_code=401,
        code="unauthorized",
        message="Invalid tenant, email, or password.",
    )
    assert first_response.headers["X-RateLimit-Limit"] == "2"
    assert first_response.headers["X-RateLimit-Remaining"] == "1"

    assert_api_error(
        second_response,
        status_code=401,
        code="unauthorized",
        message="Invalid tenant, email, or password.",
    )
    assert second_response.headers["X-RateLimit-Limit"] == "2"
    assert second_response.headers["X-RateLimit-Remaining"] == "0"

    assert_api_error(
        limited_response,
        status_code=429,
        code="rate_limited",
        message="Rate limit exceeded. Try again later.",
    )
    assert limited_response.headers["X-RateLimit-Limit"] == "2"
    assert limited_response.headers["X-RateLimit-Remaining"] == "0"
    assert int(limited_response.headers["Retry-After"]) >= 1


def test_non_limited_routes_remain_unaffected() -> None:
    with build_client(
        LOGIN_RATE_LIMIT_REQUESTS=1,
        REGISTER_RATE_LIMIT_REQUESTS=0,
        REFRESH_RATE_LIMIT_REQUESTS=0,
    ) as client:
        response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert "X-RateLimit-Limit" not in response.headers
