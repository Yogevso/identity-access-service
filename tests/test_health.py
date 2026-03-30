from fastapi.testclient import TestClient


def test_health_endpoint_returns_service_and_database_status(client: TestClient) -> None:
    response = client.get("/api/v1/health")

    assert response.status_code == 200

    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["environment"] == "test"
    assert payload["database"]["status"] == "ok"
    assert isinstance(payload["database"]["latency_ms"], int)
