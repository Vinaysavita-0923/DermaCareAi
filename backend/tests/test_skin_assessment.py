"""
Tests for the dataset-backed skin assessment system
(POST/GET/PUT /api/v1/assessment, /assessment/history,
/assessment/profile, /assessment/recommendations).

Same isolated-test-database pattern as test_profile_journal.py.
"""
from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.connection import Base, get_db
from app.main import app

TEST_DB_PATH = "test_skin_assessment.db"
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


def make_user_and_token(email: str) -> str:
    client.post(
        "/api/v1/auth/register",
        json={"full_name": email.split("@")[0], "email": email, "password": "StrongPass1"},
    )
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": "StrongPass1"})
    return resp.json()["access_token"]


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


BASE_PAYLOAD = {
    "full_name": "Priya Sharma",
    "age": 16,
    "skin_type": "dry",
    "skin_subtype": "Extreme Dry",
    "is_sensitive": True,
    "concerns": ["acne", "redness"],
    "sensitivity_notes": "Reacts to fragrance.",
}


# ---------------------------------------------------------------------
# 1. New user submission
# ---------------------------------------------------------------------
def test_new_user_can_submit_assessment():
    token = make_user_and_token("a1@example.com")
    resp = client.post("/api/v1/assessment", json=BASE_PAYLOAD, headers=auth(token))
    assert resp.status_code == 201
    body = resp.json()
    assert body["age"] == 16
    assert body["age_group"] == "14-18"
    assert body["skin_type"] == "dry"
    assert body["skin_subtype"] == "Extreme Dry"
    assert body["is_sensitive"] is True
    assert body["concerns"] == ["acne", "redness"]
    assert "history_id" in body


def test_full_name_is_written_to_user_not_duplicated():
    token = make_user_and_token("a2@example.com")
    client.post("/api/v1/assessment", json=BASE_PAYLOAD, headers=auth(token))
    me = client.get("/api/v1/auth/me", headers=auth(token)).json()
    assert me["full_name"] == "Priya Sharma"


# ---------------------------------------------------------------------
# 2. Existing user update (PUT, partial, no new history row)
# ---------------------------------------------------------------------
def test_existing_user_can_update_without_new_history_row():
    token = make_user_and_token("a3@example.com")
    client.post("/api/v1/assessment", json=BASE_PAYLOAD, headers=auth(token))
    resp = client.put("/api/v1/assessment/me", json={"sensitivity_notes": "Updated notes."}, headers=auth(token))
    assert resp.status_code == 200
    assert resp.json()["sensitivity_notes"] == "Updated notes."
    assert resp.json()["skin_type"] == "dry"  # untouched field preserved

    history = client.get("/api/v1/assessment/history", headers=auth(token)).json()
    assert len(history) == 1  # PUT did not append a new snapshot


def test_post_always_appends_a_new_history_row():
    token = make_user_and_token("a4@example.com")
    client.post("/api/v1/assessment", json=BASE_PAYLOAD, headers=auth(token))
    client.post("/api/v1/assessment", json={**BASE_PAYLOAD, "age": 20}, headers=auth(token))
    history = client.get("/api/v1/assessment/history", headers=auth(token)).json()
    assert len(history) == 2
    assert history[0]["age"] == 20  # newest first


# ---------------------------------------------------------------------
# 3-5. Sensitivity tri-state
# ---------------------------------------------------------------------
def test_sensitivity_true():
    token = make_user_and_token("a5@example.com")
    resp = client.post("/api/v1/assessment", json={**BASE_PAYLOAD, "is_sensitive": True}, headers=auth(token))
    assert resp.json()["is_sensitive"] is True


def test_sensitivity_false():
    token = make_user_and_token("a6@example.com")
    resp = client.post("/api/v1/assessment", json={**BASE_PAYLOAD, "is_sensitive": False}, headers=auth(token))
    assert resp.json()["is_sensitive"] is False


def test_sensitivity_not_sure_shows_both_states_in_guidance():
    payload = dict(BASE_PAYLOAD)
    del payload["is_sensitive"]
    token = make_user_and_token("a7@example.com")
    client.post("/api/v1/assessment", json=payload, headers=auth(token))
    profile_resp = client.get("/api/v1/assessment/me", headers=auth(token))
    assert profile_resp.json()["is_sensitive"] is None

    guidance = client.get("/api/v1/assessment/profile", headers=auth(token)).json()
    assert set(guidance["sensitivity_considered"]) == {"sensitive", "not sensitive"}
    acne = next(c for c in guidance["concerns_with_guidance"] if c["concern"] == "Acne")
    variant_keys = acne["variants"].keys()
    assert any(k.startswith("Yes|") for k in variant_keys)
    assert any(k.startswith("No|") for k in variant_keys)


# ---------------------------------------------------------------------
# 6. Multiple concern selection
# ---------------------------------------------------------------------
def test_multiple_concerns_selected_and_matched():
    token = make_user_and_token("a8@example.com")
    payload = {**BASE_PAYLOAD, "concerns": ["acne", "wrinkles", "dark_circles"]}
    client.post("/api/v1/assessment", json=payload, headers=auth(token))
    guidance = client.get("/api/v1/assessment/profile", headers=auth(token)).json()
    labels = {c["concern"] for c in guidance["concerns_with_guidance"]}
    assert labels == {"Acne", "Wrinkles", "Dark Circles"}


# ---------------------------------------------------------------------
# 7. Invalid age
# ---------------------------------------------------------------------
def test_invalid_age_rejected():
    token = make_user_and_token("a9@example.com")
    resp = client.post("/api/v1/assessment", json={**BASE_PAYLOAD, "age": -5}, headers=auth(token))
    assert resp.status_code == 422

    resp2 = client.post("/api/v1/assessment", json={**BASE_PAYLOAD, "age": 999}, headers=auth(token))
    assert resp2.status_code == 422


def test_very_young_age_clamped_to_youngest_bracket_with_note():
    token = make_user_and_token("a10@example.com")
    resp = client.post("/api/v1/assessment", json={**BASE_PAYLOAD, "age": 5}, headers=auth(token))
    assert resp.status_code == 201
    body = resp.json()
    assert body["age_group"] == "14-18"
    assert body["age_group_note"] is not None


# ---------------------------------------------------------------------
# 8. Missing optional fields
# ---------------------------------------------------------------------
def test_missing_optional_fields_still_succeeds():
    token = make_user_and_token("a11@example.com")
    resp = client.post("/api/v1/assessment", json={"age": 30, "skin_type": "oily"}, headers=auth(token))
    assert resp.status_code == 201
    body = resp.json()
    assert body["skin_subtype"] is None
    assert body["concerns"] is None


def test_subtype_omitted_shows_both_subtypes_in_guidance():
    token = make_user_and_token("a12@example.com")
    client.post("/api/v1/assessment", json={"age": 30, "skin_type": "combination"}, headers=auth(token))
    guidance = client.get("/api/v1/assessment/profile", headers=auth(token)).json()
    assert len(guidance["subtypes_considered"]) == 2


# ---------------------------------------------------------------------
# 9. Dataset matching — exact, deterministic row check
# ---------------------------------------------------------------------
def test_dataset_matching_returns_exact_known_row():
    token = make_user_and_token("a13@example.com")
    payload = {
        "age": 16,
        "skin_type": "balanced",
        "skin_subtype": "Normal to Dry",
        "is_sensitive": True,
        "concerns": ["acne"],
    }
    client.post("/api/v1/assessment", json=payload, headers=auth(token))
    guidance = client.get("/api/v1/assessment/profile", headers=auth(token)).json()
    acne = next(c for c in guidance["concerns_with_guidance"] if c["concern"] == "Acne")
    rows = acne["variants"]["Yes|Normal to Dry"]
    comedonal = next(r for r in rows if r["internal_type"] == "Comedonal")
    assert comedonal["ingredients"] == "Zinc PCA + Benzoyl Peroxide + Salicylic Acid"
    assert comedonal["concentrations"] == "2.5% + 2% + 1%"


def test_concern_with_no_dataset_coverage_is_reported_not_invented():
    token = make_user_and_token("a14@example.com")
    payload = {**BASE_PAYLOAD, "concerns": ["oiliness"]}  # legacy tag, not in the dataset's 10
    client.post("/api/v1/assessment", json=payload, headers=auth(token))
    guidance = client.get("/api/v1/assessment/profile", headers=auth(token)).json()
    assert guidance["concerns_with_guidance"] == []
    assert any("oiliness" in note for note in guidance["notes"])


# ---------------------------------------------------------------------
# 10. Product recommendation integration
# ---------------------------------------------------------------------
def test_assessment_recommendations_includes_products_and_guidance():
    token = make_user_and_token("a15@example.com")
    client.post("/api/v1/assessment", json=BASE_PAYLOAD, headers=auth(token))
    resp = client.get("/api/v1/assessment/recommendations", headers=auth(token))
    assert resp.status_code == 200
    body = resp.json()
    assert "personalized_profile" in body
    assert "products" in body
    assert "disclaimer" in body["products"]


def test_recommendations_404_without_assessment():
    token = make_user_and_token("a16@example.com")
    resp = client.get("/api/v1/assessment/recommendations", headers=auth(token))
    assert resp.status_code == 404


# ---------------------------------------------------------------------
# 11. Authentication and cross-user isolation
# ---------------------------------------------------------------------
def test_requires_authentication():
    assert client.post("/api/v1/assessment", json=BASE_PAYLOAD).status_code == 401
    assert client.get("/api/v1/assessment/me").status_code == 401
    assert client.get("/api/v1/assessment/history").status_code == 401


def test_users_cannot_see_each_others_history():
    token_a = make_user_and_token("a17@example.com")
    token_b = make_user_and_token("a18@example.com")
    client.post("/api/v1/assessment", json=BASE_PAYLOAD, headers=auth(token_a))

    history_b = client.get("/api/v1/assessment/history", headers=auth(token_b)).json()
    assert history_b == []

    profile_b = client.get("/api/v1/assessment/me", headers=auth(token_b))
    assert profile_b.status_code == 404


# ---------------------------------------------------------------------
# Subtype / skin-type cross-validation
# ---------------------------------------------------------------------
def test_mismatched_subtype_rejected():
    token = make_user_and_token("a19@example.com")
    resp = client.post(
        "/api/v1/assessment",
        json={"age": 25, "skin_type": "dry", "skin_subtype": "T-Zone Oily Cheeks Dry"},
        headers=auth(token),
    )
    assert resp.status_code == 422


def test_subtype_rejected_when_skin_type_unsure():
    token = make_user_and_token("a20@example.com")
    resp = client.post(
        "/api/v1/assessment",
        json={"age": 25, "skin_type": "unsure", "skin_subtype": "Extreme Dry"},
        headers=auth(token),
    )
    assert resp.status_code == 422


def test_unknown_concern_tag_rejected():
    token = make_user_and_token("a21@example.com")
    resp = client.post(
        "/api/v1/assessment",
        json={**BASE_PAYLOAD, "concerns": ["not_a_real_concern"]},
        headers=auth(token),
    )
    assert resp.status_code == 422
