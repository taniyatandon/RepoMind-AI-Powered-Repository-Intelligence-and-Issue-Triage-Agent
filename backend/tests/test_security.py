from datetime import timedelta
import pytest
from fastapi import HTTPException
from app.models.user import User
from app.security import (
    create_access_token,
    decode_access_token,
    get_password_hash,
    verify_password,
)

def test_password_hashing_and_verification():
    raw = "MySecretPassword!2026"
    hashed = get_password_hash(raw)
    assert hashed != raw
    assert "$argon2" in hashed
    assert verify_password(raw, hashed) is True
    assert verify_password("WrongSecretPassword", hashed) is False

def test_jwt_create_and_decode_valid():
    token = create_access_token({"sub": "user@repomind.io", "custom": "value"})
    payload = decode_access_token(token)
    assert payload["sub"] == "user@repomind.io"
    assert payload["custom"] == "value"
    assert "exp" in payload

def test_jwt_decode_expired_or_invalid():
    # Expired token (negative delta)
    expired_token = create_access_token(
        {"sub": "user@repomind.io"},
        expires_delta=timedelta(seconds=-10),
    )
    with pytest.raises(HTTPException) as exc_info:
        decode_access_token(expired_token)
    assert exc_info.value.status_code == 401

    # Completely invalid signature
    with pytest.raises(HTTPException) as exc_info_inv:
        decode_access_token("not.a.valid.jwt.token")
    assert exc_info_inv.value.status_code == 401

def test_inactive_user_access_rejected(client, db_session):
    user = User(
        email="inactive@example.com",
        username="inactive",
        password_hash=get_password_hash("pass123"),
        is_active=False,
    )
    db_session.add(user)
    db_session.commit()

    token = create_access_token({"sub": user.email, "user_id": user.id})
    res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 400
    assert "inactive" in res.json()["detail"].lower()
