import pytest

def test_register_user_success(client):
    response = client.post(
        "/api/auth/register",
        json={
            "email": "alice@example.com",
            "password": "strongpassword123",
            "username": "alice",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "alice@example.com"
    assert data["username"] == "alice"
    assert "id" in data
    assert data["is_active"] is True

def test_register_user_duplicate_email(client, test_user):
    response = client.post(
        "/api/auth/register",
        json={
            "email": test_user.email,
            "password": "password123",
            "username": "duplicate_user",
        },
    )
    assert response.status_code == 400
    assert "already registered" in response.json()["detail"].lower()

def test_register_user_invalid_email(client):
    response = client.post(
        "/api/auth/register",
        json={
            "email": "not-an-email",
            "password": "validpassword123",
        },
    )
    assert response.status_code == 422

def test_register_user_short_password(client):
    response = client.post(
        "/api/auth/register",
        json={
            "email": "shortpass@example.com",
            "password": "123",
        },
    )
    assert response.status_code == 422

def test_login_success(client, test_user):
    response = client.post(
        "/api/auth/login",
        json={
            "email": test_user.email,
            "password": "securepass123",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == test_user.email

def test_login_invalid_password(client, test_user):
    response = client.post(
        "/api/auth/login",
        json={
            "email": test_user.email,
            "password": "wrongpassword",
        },
    )
    assert response.status_code == 401
    assert "incorrect" in response.json()["detail"].lower()

def test_login_nonexistent_user(client):
    response = client.post(
        "/api/auth/login",
        json={
            "email": "nobody@nowhere.com",
            "password": "anypassword",
        },
    )
    assert response.status_code == 401
    assert "incorrect" in response.json()["detail"].lower()

def test_get_current_user_me_success(client, auth_headers, test_user):
    response = client.get("/api/auth/me", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == test_user.email
    assert data["username"] == test_user.username

def test_get_current_user_me_unauthorized(client):
    response = client.get("/api/auth/me")
    assert response.status_code == 401
