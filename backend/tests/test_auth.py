from datetime import datetime, timedelta, timezone

import jwt

from app import config
from app.models import User
from tests.conftest import auth_header, register


def test_register_returns_token_and_no_password_data(client):
    data = register(client)
    assert data["access_token"]
    assert data["user"]["email"] == "a@example.com"
    assert "password" not in str(data).lower()
    assert "hash" not in str(data).lower()


def test_password_is_stored_hashed(client, db):
    register(client, password="password123")
    user = db.query(User).one()
    assert user.password_hash != "password123"
    assert user.password_hash.startswith("$2")  # bcrypt marker


def test_duplicate_email_rejected_case_insensitive(client):
    register(client, email="a@example.com")
    response = client.post(
        "/auth/register",
        json={"email": "A@Example.com", "full_name": "Other", "password": "password123"},
    )
    assert response.status_code == 409


def test_register_validation(client):
    short_password = {"email": "a@example.com", "full_name": "A", "password": "short"}
    bad_email = {"email": "not-an-email", "full_name": "A", "password": "password123"}
    assert client.post("/auth/register", json=short_password).status_code == 422
    assert client.post("/auth/register", json=bad_email).status_code == 422


def test_login_success(client):
    register(client)
    response = client.post("/auth/login", json={"email": "a@example.com", "password": "password123"})
    assert response.status_code == 200
    assert response.json()["access_token"]


def test_login_wrong_password_and_unknown_user_give_same_error(client):
    register(client)
    wrong = client.post("/auth/login", json={"email": "a@example.com", "password": "wrongpass1"})
    unknown = client.post("/auth/login", json={"email": "nobody@example.com", "password": "password123"})
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()


def test_me_with_valid_token(client):
    token = register(client)["access_token"]
    response = client.get("/auth/me", headers=auth_header(token))
    assert response.status_code == 200
    assert response.json()["email"] == "a@example.com"


def test_me_without_or_with_bad_token_is_401(client):
    assert client.get("/auth/me").status_code == 401
    assert client.get("/auth/me", headers=auth_header("garbage")).status_code == 401


def test_token_signed_with_wrong_key_is_rejected(client):
    user_id = register(client)["user"]["id"]
    forged = jwt.encode({"sub": str(user_id)}, "some-other-secret-key-that-is-32-chars-or-more", algorithm="HS256")
    assert client.get("/auth/me", headers=auth_header(forged)).status_code == 401


def test_expired_token_is_rejected(client):
    user_id = register(client)["user"]["id"]
    expired = jwt.encode(
        {"sub": str(user_id), "exp": datetime.now(timezone.utc) - timedelta(minutes=1)},
        config.JWT_SECRET_KEY,
        algorithm=config.JWT_ALGORITHM,
    )
    assert client.get("/auth/me", headers=auth_header(expired)).status_code == 401


def test_token_for_deleted_user_is_rejected(client, db):
    token = register(client)["access_token"]
    db.delete(db.query(User).one())
    db.commit()
    assert client.get("/auth/me", headers=auth_header(token)).status_code == 401
