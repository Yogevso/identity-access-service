from __future__ import annotations

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_application


@pytest.fixture()
def client() -> Generator[TestClient, None, None]:
    settings = Settings(
        APP_NAME="Identity Access Service Test",
        APP_ENV="test",
        APP_VERSION="0.1.0-test",
        API_V1_PREFIX="/api/v1",
        DATABASE_URL="sqlite+pysqlite:///:memory:",
    )

    with TestClient(create_application(settings)) as test_client:
        yield test_client
