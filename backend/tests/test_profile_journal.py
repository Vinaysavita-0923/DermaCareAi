"""
Tests for Phase 4: profile and journal CRUD.

The cross-user isolation tests here are the point of this phase — they
prove that User B cannot read, change, or delete User A's data even
when B knows A's entry id.

Isolated test database, same pattern as the auth tests.
"""
from __future__ import annotations

import datetime
import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.connection import Base, get_db
from app.main import app

TEST_DB_PATH = "test_phase4.db"
TEST_DB_URL = f"sqlite:///{TEST_DB_PATH}"

_engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
_TestSessionLocal = sessionmaker(bind=_engine)


def _override_get_db():
    db = _TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def fresh_db():
    Base.metadata.drop_all(bind=_engine)
    Base.metadata.create_all(bind=_engine)
    app.dependency_overrides[get_db] = _override_get_db
    yield
    app.dependency_overrides.clear()


@pytest.fixture(scope="module", autouse=True)
def cleanup_file():
    yield
    _engine.dispose()
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)


client = TestClient(app)
TODAY = datetime.date.today().isoformat()


def make_user_and_token(email: str) -> str:
    client.post(
        "/api/v1/auth/register",
        json={"full_name": email.split("@")[0], "email": email, "password": "StrongPass1"},
    )
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": "StrongPass1"})
    return resp.json()["access_token"]


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------
def test_profile_requires_auth():
    assert client.get("/api/v1/profile").status_code == 401
    assert client.put("/api/v1/profile", json={"skin_type": "oily"}).status_code == 401


def test_profile_not_found_before_creation():
    token = make_user_and_token("p1@example.com")
    assert client.get("/api/v1/profile", headers=auth(token)).status_code == 404


def test_profile_create_then_read():
    token = make_user_and_token("p2@example.com")
    put = client.put(
        "/api/v1/profile",
        headers=auth(token),
        json={"skin_type": "oily", "concerns": ["acne", "redness"]},
    )
    assert put.status_code == 200
    body = put.json()
    assert body["skin_type"] == "oily"
    assert body["concerns"] == ["acne", "redness"]

    got = client.get("/api/v1/profile", headers=auth(token))
    assert got.status_code == 200
    assert got.json()["skin_type"] == "oily"


def test_profile_partial_update_preserves_other_fields():
    token = make_user_and_token("p3@example.com")
    client.put(
        "/api/v1/profile",
        headers=auth(token),
        json={"skin_type": "dry", "concerns": ["dryness"]},
    )
    # Update only skin_type — concerns must survive.
    client.put("/api/v1/profile", headers=auth(token), json={"skin_type": "combination"})
    body = client.get("/api/v1/profile", headers=auth(token)).json()
    assert body["skin_type"] == "combination"
    assert body["concerns"] == ["dryness"]


def test_profile_rejects_unknown_concern():
    token = make_user_and_token("p4@example.com")
    resp = client.put(
        "/api/v1/profile",
        headers=auth(token),
        json={"concerns": ["acne", "cancer"]},  # second is not an allowed tag
    )
    assert resp.status_code == 422


def test_profile_concurrent_create_recovers_from_race():
    """Simulate the race directly at the DB layer: insert a profile for
    the user 'behind the endpoint's back', then PUT — the endpoint's
    first insert attempt will hit the unique(user_id) constraint and
    must recover with a 200, not crash with a 500."""
    token = make_user_and_token("race@example.com")

    # Find the user's id and pre-insert a profile, imitating a second
    # concurrent request that committed first.
    from app.database.models import SkinProfile, User

    db = _TestSessionLocal()
    user = db.query(User).filter_by(email="race@example.com").one()
    db.add(SkinProfile(user_id=user.id, skin_type="dry"))
    db.commit()
    db.close()

    # Now the endpoint will try to insert (it hasn't seen the row in its
    # own session) and must recover gracefully.
    resp = client.put("/api/v1/profile", headers=auth(token), json={"skin_type": "oily"})
    assert resp.status_code == 200
    assert resp.json()["skin_type"] == "oily"


def test_empty_put_creates_default_profile():
    """A PUT with no fields on a new user still creates a usable profile
    with sensible defaults (skin_type='unsure'), rather than erroring."""
    token = make_user_and_token("emptyput@example.com")
    resp = client.put("/api/v1/profile", headers=auth(token), json={})
    assert resp.status_code == 200
    assert resp.json()["skin_type"] == "unsure"


def test_two_users_have_separate_profiles():
    token_a = make_user_and_token("pa@example.com")
    token_b = make_user_and_token("pb@example.com")
    client.put("/api/v1/profile", headers=auth(token_a), json={"skin_type": "oily"})
    client.put("/api/v1/profile", headers=auth(token_b), json={"skin_type": "dry"})

    assert client.get("/api/v1/profile", headers=auth(token_a)).json()["skin_type"] == "oily"
    assert client.get("/api/v1/profile", headers=auth(token_b)).json()["skin_type"] == "dry"


# ---------------------------------------------------------------------
# Journal — basic CRUD
# ---------------------------------------------------------------------
def test_journal_requires_auth():
    assert client.get("/api/v1/journal").status_code == 401
    assert client.post("/api/v1/journal", json={"entry_date": TODAY}).status_code == 401


def test_journal_create_and_list():
    token = make_user_and_token("j1@example.com")
    created = client.post(
        "/api/v1/journal",
        headers=auth(token),
        json={"entry_date": TODAY, "notes": "Skin felt calm", "skin_feeling_tags": ["calm"]},
    )
    assert created.status_code == 201
    entry_id = created.json()["id"]

    listing = client.get("/api/v1/journal", headers=auth(token))
    assert listing.status_code == 200
    assert len(listing.json()) == 1
    assert listing.json()[0]["id"] == entry_id


def test_journal_one_entry_per_day():
    token = make_user_and_token("j2@example.com")
    client.post("/api/v1/journal", headers=auth(token), json={"entry_date": TODAY})
    second = client.post("/api/v1/journal", headers=auth(token), json={"entry_date": TODAY})
    assert second.status_code == 409


def test_journal_future_date_rejected():
    token = make_user_and_token("j3@example.com")
    future = (datetime.date.today() + datetime.timedelta(days=5)).isoformat()
    resp = client.post("/api/v1/journal", headers=auth(token), json={"entry_date": future})
    assert resp.status_code == 422


def test_journal_update_and_delete():
    token = make_user_and_token("j4@example.com")
    entry_id = client.post(
        "/api/v1/journal", headers=auth(token), json={"entry_date": TODAY, "notes": "first"}
    ).json()["id"]

    updated = client.put(
        f"/api/v1/journal/{entry_id}", headers=auth(token), json={"notes": "updated note"}
    )
    assert updated.status_code == 200
    assert updated.json()["notes"] == "updated note"

    deleted = client.delete(f"/api/v1/journal/{entry_id}", headers=auth(token))
    assert deleted.status_code == 204
    assert client.get(f"/api/v1/journal/{entry_id}", headers=auth(token)).status_code == 404


def test_journal_invalid_tag_rejected():
    token = make_user_and_token("j5@example.com")
    resp = client.post(
        "/api/v1/journal",
        headers=auth(token),
        json={"entry_date": TODAY, "skin_feeling_tags": ["nonsense_tag"]},
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------
# Cross-user isolation — the core of this phase
# ---------------------------------------------------------------------
def test_user_b_cannot_read_user_a_entry():
    token_a = make_user_and_token("iso_a@example.com")
    token_b = make_user_and_token("iso_b@example.com")

    a_entry_id = client.post(
        "/api/v1/journal", headers=auth(token_a), json={"entry_date": TODAY, "notes": "A's secret"}
    ).json()["id"]

    # B knows the id and asks for it directly -> must look like it doesn't exist.
    resp = client.get(f"/api/v1/journal/{a_entry_id}", headers=auth(token_b))
    assert resp.status_code == 404


def test_user_b_cannot_update_user_a_entry():
    token_a = make_user_and_token("iso_a2@example.com")
    token_b = make_user_and_token("iso_b2@example.com")

    a_entry_id = client.post(
        "/api/v1/journal", headers=auth(token_a), json={"entry_date": TODAY, "notes": "original"}
    ).json()["id"]

    resp = client.put(
        f"/api/v1/journal/{a_entry_id}", headers=auth(token_b), json={"notes": "hacked"}
    )
    assert resp.status_code == 404

    # And A's entry is genuinely untouched.
    still = client.get(f"/api/v1/journal/{a_entry_id}", headers=auth(token_a))
    assert still.json()["notes"] == "original"


def test_user_b_cannot_delete_user_a_entry():
    token_a = make_user_and_token("iso_a3@example.com")
    token_b = make_user_and_token("iso_b3@example.com")

    a_entry_id = client.post(
        "/api/v1/journal", headers=auth(token_a), json={"entry_date": TODAY}
    ).json()["id"]

    resp = client.delete(f"/api/v1/journal/{a_entry_id}", headers=auth(token_b))
    assert resp.status_code == 404

    # A's entry still exists.
    assert client.get(f"/api/v1/journal/{a_entry_id}", headers=auth(token_a)).status_code == 200


def test_user_b_list_never_shows_user_a_entries():
    token_a = make_user_and_token("iso_a4@example.com")
    token_b = make_user_and_token("iso_b4@example.com")

    client.post("/api/v1/journal", headers=auth(token_a), json={"entry_date": TODAY, "notes": "A"})

    b_list = client.get("/api/v1/journal", headers=auth(token_b))
    assert b_list.status_code == 200
    assert b_list.json() == []  # B sees nothing of A's
