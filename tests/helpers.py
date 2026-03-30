from __future__ import annotations


def assert_api_error(
    response,
    *,
    status_code: int,
    code: str,
    message: str,
) -> dict:
    assert response.status_code == status_code
    payload = response.json()
    assert payload["error"]["code"] == code
    assert payload["error"]["message"] == message
    return payload["error"]
