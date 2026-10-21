"""Small helpers shared by API tests."""

from fastapi.testclient import TestClient


def register_and_login(
    client: TestClient,
    email: str,
    password: str = "password123",
):
    """Create account + return (user_json, bearer_headers)."""
    reg = client.post(
        "/auth/register",
        json={"email": email, "password": password, "name": "Test"},
    )
    assert reg.status_code == 201, reg.text
    user = reg.json()
    login = client.post(
        "/auth/login",
        json={"email": email, "password": password},
    )
    assert login.status_code == 200, login.text
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    return user, headers
