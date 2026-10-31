"""
Tests for Phase 3: authentication.

Runs entirely against an isolated SQLite file created fresh for this
test session and deleted afterward. The real app's dependency on
get_db is overridden for the duration of these tests only — real
skincare.db is never opened.
"""
from __future__ import annotations

import os
import time

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings
from app.database.connection import Base, get_db
from app.main import app

TEST_DB_PATH = "test_phase3_auth.db"
TEST_DB_URL = f"sqlite:///{TEST_DB_PATH}"

_test_engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
_TestSessionLocal = sessionmaker(bind=_test_engine)


def _override_get_db():
    db = _TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def isolated_test_database():
    """Fresh tables before every test, so tests never depend on order
    or leak state into each other."""
    Base.metadata.drop_all(bind=_test_engine)
    Base.metadata.create_all(bind=_test_engine)
    app.dependency_overrides[get_db] = _override_get_db
    yield
    app.dependency_overrides.clear()


@pytest.fixture(scope="module", autouse=True)
def cleanup_test_db_file():
    yield
    _test_engine.dispose()
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)


client = TestClient(app)

VALID_USER = {
    "full_name": "Asha Rao",
    "email": "asha@example.com",
    "password": "StrongPass1",
}


def register(payload=None):
    return client.post("/api/v1/auth/register", json=payload or VALID_USER)


def login(email=None, password=None):
    return client.post(
        "/api/v1/auth/login",
        json={"email": email or VALID_USER["email"], "password": password or VALID_USER["password"]},
    )


# ---------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------
def test_successful_registration():
    response = register()
    assert response.status_code == 201
    body = response.json()
    assert body["email"] == VALID_USER["email"]
    assert body["full_name"] == VALID_USER["full_name"]
    assert "hashed_password" not in body
    assert "password" not in body


def test_duplicate_email_registration_is_rejected():
    first = register()
    assert first.status_code == 201
    second = register()
    assert second.status_code == 409


def test_invalid_email_is_rejected():
    bad = {**VALID_USER, "email": "not-an-email"}
    response = register(bad)
    assert response.status_code == 422


@pytest.mark.parametrize(
    "bad_password,reason",
    [
        ("short1", "too short"),
        ("alllettersnodigits", "no digit"),
        ("12345678", "no letter"),
    ],
)
def test_weak_password_is_rejected(bad_password, reason):
    bad = {**VALID_USER, "email": f"{bad_password}@example.com", "password": bad_password}
    response = register(bad)
    assert response.status_code == 422, f"expected rejection for: {reason}"


# ---------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------
def test_successful_login_returns_token_and_user():
    register()
    response = login()
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert len(body["access_token"]) > 20
    assert body["user"]["email"] == VALID_USER["email"]
    assert "hashed_password" not in body["user"]


def test_wrong_password_is_rejected():
    register()
    response = login(password="TotallyWrong1")
    assert response.status_code == 401


def test_nonexistent_email_gives_same_generic_error_as_wrong_password():
    register()
    wrong_password_response = login(password="TotallyWrong1")
    nonexistent_email_response = login(email="nobody@example.com", password="Whatever1")

    assert wrong_password_response.status_code == nonexistent_email_response.status_code == 401
    assert wrong_password_response.json()["detail"] == nonexistent_email_response.json()["detail"]


# ---------------------------------------------------------------------
# /me — protected route
# ---------------------------------------------------------------------
def test_me_without_token_is_rejected():
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401


def test_me_with_valid_token_returns_the_right_user():
    register()
    token = login().json()["access_token"]
    response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["email"] == VALID_USER["email"]


def test_me_with_garbage_token_is_rejected():
    response = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer not-a-real-token"})
    assert response.status_code == 401


def test_me_with_expired_token_is_rejected():
    settings = get_settings()
    expired_payload = {
        "sub": "1",
        "jti": "expired-test-jti",
        "iat": int(time.time()) - 7200,
        "exp": int(time.time()) - 3600,  # expired one hour ago
    }
    expired_token = jwt.encode(expired_payload, settings.secret_key, algorithm=settings.jwt_algorithm)
    response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {expired_token}"})
    assert response.status_code == 401


def test_token_signed_with_wrong_secret_is_rejected():
    forged_payload = {"sub": "1", "jti": "forged-jti", "iat": int(time.time()), "exp": int(time.time()) + 3600}
    forged_token = jwt.encode(forged_payload, "not-the-real-secret-key", algorithm="HS256")
    response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {forged_token}"})
    assert response.status_code == 401


# ---------------------------------------------------------------------
# Logout
# ---------------------------------------------------------------------
def test_logout_then_reuse_of_same_token_is_rejected():
    register()
    token = login().json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    me_before = client.get("/api/v1/auth/me", headers=headers)
    assert me_before.status_code == 200

    logout_response = client.post("/api/v1/auth/logout", headers=headers)
    assert logout_response.status_code == 200

    me_after = client.get("/api/v1/auth/me", headers=headers)
    assert me_after.status_code == 401, "a logged-out token must no longer work"


def test_logout_without_token_is_rejected():
    response = client.post("/api/v1/auth/logout")
    assert response.status_code == 401


def test_logging_out_twice_does_not_error():
    register()
    token = login().json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    first = client.post("/api/v1/auth/logout", headers=headers)
    assert first.status_code == 200
    # The dependency rejects the token on the second call before the
    # route body even runs — that's expected and correct (you can't
    # log out twice with the same already-dead token).
    second = client.post("/api/v1/auth/logout", headers=headers)
    assert second.status_code == 401


# ---------------------------------------------------------------------
# Cross-user isolation — "User A accessing User B's data"
# ---------------------------------------------------------------------
def test_two_users_tokens_only_ever_return_their_own_identity():
    """There is no user-id parameter anywhere in this API for a client
    to tamper with — identity comes only from the verified token. This
    proves that structurally: two different users, two different
    tokens, and each token can only ever produce its own owner's data
    from /me, never the other user's."""
    register({**VALID_USER, "email": "userA@example.com", "full_name": "User A"})
    register({**VALID_USER, "email": "userB@example.com", "full_name": "User B"})

    token_a = login(email="userA@example.com").json()["access_token"]
    token_b = login(email="userB@example.com").json()["access_token"]

    me_a = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token_a}"}).json()
    me_b = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token_b}"}).json()

    assert me_a["email"] == "userA@example.com"
    assert me_b["email"] == "userB@example.com"
    assert me_a["id"] != me_b["id"]


def test_ensure_owner_rejects_mismatched_user():
    """Unit test for the ownership-check helper every Phase 4+ resource
    endpoint will call. There are no real resource endpoints yet
    (profile/journal CRUD is Phase 4) — this is the piece Phase 3 is
    responsible for delivering, tested directly."""
    from fastapi import HTTPException

    from app.core.security import ensure_owner
    from app.database.models import User

    owner = User(id=1, email="owner@example.com")
    stranger = User(id=2, email="stranger@example.com")

    ensure_owner(owner.id, owner)  # must not raise

    with pytest.raises(HTTPException) as exc_info:
        ensure_owner(owner.id, stranger)
    assert exc_info.value.status_code == 404  # not 403 — see ensure_owner's docstring
