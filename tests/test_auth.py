from fastapi.testclient import TestClient


def test_register_and_login(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": "user@example.com", "password": "secret123", "full_name": "Test User"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "user@example.com"
    assert body["role"] == "user"
    assert "hashed_password" not in body

    login = client.post(
        "/api/v1/auth/login",
        data={"username": "user@example.com", "password": "secret123"},
    )
    assert login.status_code == 200
    tokens = login.json()
    assert tokens["token_type"] == "bearer"
    assert tokens["access_token"]
    assert tokens["refresh_token"]


def test_duplicate_register_conflict(client: TestClient) -> None:
    payload = {"email": "dup@example.com", "password": "secret123"}
    assert client.post("/api/v1/auth/register", json=payload).status_code == 201
    assert client.post("/api/v1/auth/register", json=payload).status_code == 409


def test_login_wrong_password(client: TestClient) -> None:
    client.post("/api/v1/auth/register", json={"email": "user@example.com", "password": "secret123"})
    response = client.post(
        "/api/v1/auth/login",
        data={"username": "user@example.com", "password": "wrongpass"},
    )
    assert response.status_code == 401


def test_refresh_token(client: TestClient) -> None:
    client.post("/api/v1/auth/register", json={"email": "user@example.com", "password": "secret123"})
    login = client.post(
        "/api/v1/auth/login",
        data={"username": "user@example.com", "password": "secret123"},
    )
    refresh = client.post("/api/v1/auth/refresh", json={"refresh_token": login.json()["refresh_token"]})
    assert refresh.status_code == 200
    assert refresh.json()["access_token"]


def test_logout_requires_authentication_and_returns_no_content(client: TestClient) -> None:
    client.post("/api/v1/auth/register", json={"email": "user@example.com", "password": "secret123"})
    login = client.post(
        "/api/v1/auth/login",
        data={"username": "user@example.com", "password": "secret123"},
    )

    response = client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": f"Bearer {login.json()['access_token']}"},
    )

    assert response.status_code == 204
    assert response.content == b""
    assert client.post("/api/v1/auth/logout").status_code == 401
