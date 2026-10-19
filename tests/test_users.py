from fastapi.testclient import TestClient

from app.models.user import User


def _auth_header(client: TestClient, email: str, password: str) -> dict[str, str]:
    login = client.post("/api/v1/auth/login", data={"username": email, "password": password})
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def test_me_requires_token(client: TestClient) -> None:
    response = client.get("/api/v1/users/me")
    assert response.status_code == 401


def test_me_with_token(client: TestClient) -> None:
    client.post("/api/v1/auth/register", json={"email": "user@example.com", "password": "secret123"})
    headers = _auth_header(client, "user@example.com", "secret123")
    response = client.get("/api/v1/users/me", headers=headers)
    assert response.status_code == 200
    assert response.json()["email"] == "user@example.com"


def test_user_cannot_list_users(client: TestClient) -> None:
    client.post("/api/v1/auth/register", json={"email": "user@example.com", "password": "secret123"})
    headers = _auth_header(client, "user@example.com", "secret123")
    response = client.get("/api/v1/users", headers=headers)
    assert response.status_code == 403


def test_admin_can_list_users(client: TestClient, admin_user: User) -> None:
    headers = _auth_header(client, admin_user.email, "adminpass")
    response = client.get("/api/v1/users", headers=headers)
    assert response.status_code == 200
    emails = [item["email"] for item in response.json()]
    assert admin_user.email in emails
