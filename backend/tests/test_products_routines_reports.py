"""
Tests for Phase 7: product catalog, routine CRUD/logging, and reports.
"""
from __future__ import annotations

import datetime
import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.connection import Base, get_db
from app.database.models import Ingredient, Product, ProductIngredient
from app.main import app

TEST_DB_PATH = "test_phase7.db"
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


def token(email: str) -> str:
    client.post(
        "/api/v1/auth/register",
        json={"full_name": email.split("@")[0], "email": email, "password": "StrongPass1"},
    )
    return client.post(
        "/api/v1/auth/login", json={"email": email, "password": "StrongPass1"}
    ).json()["access_token"]


def auth(t: str) -> dict:
    return {"Authorization": f"Bearer {t}"}


def seed_products(n=1):
    db = _TestSessionLocal()
    ing = Ingredient(name="Niacinamide", description="A vitamin B3 derivative.")
    db.add(ing)
    db.commit()
    product_ids = []
    for i in range(n):
        p = Product(
            name=f"Gentle Cleanser {i}",
            brand="SampleBrand",
            category="cleanser",
            is_sample_data=True,
            source="demo data for development",
        )
        db.add(p)
        db.commit()
        db.add(ProductIngredient(product_id=p.id, ingredient_id=ing.id))
        db.commit()
        product_ids.append(p.id)
    db.close()
    return product_ids


# ---------------------------------------------------------------------
# Products
# ---------------------------------------------------------------------
def test_products_requires_auth():
    assert client.get("/api/v1/products").status_code == 401


def test_list_products_marks_sample_data():
    seed_products(2)
    t = token("prod1@example.com")
    resp = client.get("/api/v1/products", headers=auth(t))
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 2
    assert all(p["is_sample_data"] is True for p in body)
    assert all(p["source"] for p in body)  # every item has a source string


def test_search_products_by_name():
    seed_products(1)
    t = token("prod2@example.com")
    resp = client.get("/api/v1/products", headers=auth(t), params={"q": "Gentle"})
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    resp2 = client.get("/api/v1/products", headers=auth(t), params={"q": "NoSuchThing"})
    assert resp2.json() == []


def test_get_product_detail_includes_ingredients():
    ids = seed_products(1)
    t = token("prod3@example.com")
    resp = client.get(f"/api/v1/products/{ids[0]}", headers=auth(t))
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["ingredients"]) == 1
    assert body["ingredients"][0]["name"] == "Niacinamide"


def test_get_nonexistent_product_404():
    t = token("prod4@example.com")
    assert client.get("/api/v1/products/9999", headers=auth(t)).status_code == 404


# ---------------------------------------------------------------------
# Routines
# ---------------------------------------------------------------------
def test_routines_requires_auth():
    assert client.get("/api/v1/routines").status_code == 401


def test_create_and_list_routine():
    t = token("r1@example.com")
    created = client.post(
        "/api/v1/routines", headers=auth(t), json={"routine_type": "morning", "items": []}
    )
    assert created.status_code == 201
    assert created.json()["routine_type"] == "morning"

    listing = client.get("/api/v1/routines", headers=auth(t))
    assert len(listing.json()) == 1


def test_routine_with_items():
    product_ids = seed_products(1)
    t = token("r2@example.com")
    resp = client.post(
        "/api/v1/routines",
        headers=auth(t),
        json={
            "routine_type": "night",
            "items": [{"product_id": product_ids[0], "step_order": 1, "notes": "after cleansing"}],
        },
    )
    assert resp.status_code == 201
    assert len(resp.json()["items"]) == 1
    assert resp.json()["items"][0]["product_id"] == product_ids[0]


def test_log_routine_day_and_upsert():
    t = token("r3@example.com")
    rid = client.post(
        "/api/v1/routines", headers=auth(t), json={"routine_type": "morning", "items": []}
    ).json()["id"]

    log1 = client.post(f"/api/v1/routines/{rid}/log", headers=auth(t), json={"log_date": TODAY, "completed": True})
    assert log1.status_code == 200
    assert log1.json()["completed"] is True

    # Logging the same date again updates rather than erroring (upsert).
    log2 = client.post(f"/api/v1/routines/{rid}/log", headers=auth(t), json={"log_date": TODAY, "completed": False})
    assert log2.status_code == 200
    assert log2.json()["completed"] is False
    assert log2.json()["id"] == log1.json()["id"]  # same row, not a duplicate


def test_log_future_date_rejected():
    t = token("r4@example.com")
    rid = client.post(
        "/api/v1/routines", headers=auth(t), json={"routine_type": "morning", "items": []}
    ).json()["id"]
    future = (datetime.date.today() + datetime.timedelta(days=2)).isoformat()
    resp = client.post(f"/api/v1/routines/{rid}/log", headers=auth(t), json={"log_date": future})
    assert resp.status_code == 422


# ---------------------------------------------------------------------
# Cross-user isolation for routines
# ---------------------------------------------------------------------
def test_user_b_cannot_see_or_log_user_a_routine():
    ta = token("ra@example.com")
    tb = token("rb@example.com")
    rid = client.post(
        "/api/v1/routines", headers=auth(ta), json={"routine_type": "morning", "items": []}
    ).json()["id"]

    assert client.get(f"/api/v1/routines/{rid}", headers=auth(tb)).status_code == 404
    assert client.post(
        f"/api/v1/routines/{rid}/log", headers=auth(tb), json={"log_date": TODAY}
    ).status_code == 404
    assert client.delete(f"/api/v1/routines/{rid}", headers=auth(tb)).status_code == 404
    # still intact for A
    assert client.get(f"/api/v1/routines/{rid}", headers=auth(ta)).status_code == 200


def test_routine_list_only_shows_own():
    ta = token("rc@example.com")
    tb = token("rd@example.com")
    client.post("/api/v1/routines", headers=auth(ta), json={"routine_type": "night", "items": []})
    assert client.get("/api/v1/routines", headers=auth(tb)).json() == []


# ---------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------
def test_reports_requires_auth():
    assert client.get("/api/v1/reports/summary").status_code == 401


def test_report_counts_journal_and_routine_activity():
    t = token("rep1@example.com")

    client.post(
        "/api/v1/journal", headers=auth(t),
        json={"entry_date": TODAY, "skin_feeling_tags": ["calm", "dry"]},
    )
    rid = client.post(
        "/api/v1/routines", headers=auth(t), json={"routine_type": "morning", "items": []}
    ).json()["id"]
    client.post(f"/api/v1/routines/{rid}/log", headers=auth(t), json={"log_date": TODAY, "completed": True})

    resp = client.get("/api/v1/reports/summary", headers=auth(t))
    assert resp.status_code == 200
    body = resp.json()
    assert body["journal_entry_count"] == 1
    assert body["feeling_tag_counts"] == {"calm": 1, "dry": 1}
    assert body["routine_completion"][0]["days_logged"] == 1
    assert body["routine_completion"][0]["days_completed"] == 1
    assert body["routine_completion"][0]["completion_rate"] == 1.0
    assert "not a measure of clinical improvement" in body["disclaimer"].lower()


def test_report_only_reflects_own_data():
    ta = token("rep_a@example.com")
    tb = token("rep_b@example.com")
    client.post(
        "/api/v1/journal", headers=auth(ta), json={"entry_date": TODAY, "notes": "A's entry"}
    )
    body_b = client.get("/api/v1/reports/summary", headers=auth(tb)).json()
    assert body_b["journal_entry_count"] == 0


def test_report_with_no_activity_is_zeroed_not_erroring():
    t = token("rep_empty@example.com")
    resp = client.get("/api/v1/reports/summary", headers=auth(t))
    assert resp.status_code == 200
    body = resp.json()
    assert body["journal_entry_count"] == 0
    assert body["feeling_tag_counts"] == {}
    assert body["routine_completion"] == []
