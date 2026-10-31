"""
Tests for the sample catalog seed and the profile-based recommendations.

These prove the matching/filtering rules behave as written (sensitivity,
pregnancy caution, avoided ingredients) and that the seed is idempotent.
They do not prove any product is right for a real person.
"""
from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.connection import Base, get_db
from app.database.models import (
    Ingredient,
    Product,
    ProductIngredient,
    Routine,
    RoutineItem,
    RoutineType,
    User,
)
from app.knowledge_base.skincare_catalog import (
    ACTIVE_INGREDIENTS,
    INGREDIENTS,
    PREGNANCY_CAUTION_INGREDIENTS,
    PRODUCTS,
    validate_catalog,
)
from app.main import app
from app.services.agent_tools import ToolContext, run_tool
from app.services.branded_catalog import unique_eligible_products
from scripts.seed_demo_products import seed_catalog

TEST_DB_PATH = "test_catalog.db"
_engine = create_engine(f"sqlite:///{TEST_DB_PATH}", connect_args={"check_same_thread": False})
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


def token(email: str = "a@example.com") -> str:
    client.post("/api/v1/auth/register", json={"full_name": "A", "email": email, "password": "StrongPass1"})
    return client.post("/api/v1/auth/login", json={"email": email, "password": "StrongPass1"}).json()["access_token"]


def auth(t: str) -> dict:
    return {"Authorization": f"Bearer {t}"}


def seed() -> dict:
    db = _TestSessionLocal()
    try:
        return seed_catalog(db)
    finally:
        db.close()


def set_profile(t: str, **body):
    r = client.put("/api/v1/profile", json=body, headers=auth(t))
    assert r.status_code == 200, r.text


def recs(t: str, **params):
    return client.get("/api/v1/recommendations", params=params, headers=auth(t))


def ingredients_of(rec: dict) -> set[str]:
    return {i for p in rec["matches"] for i in p["ingredients"]}


# ---------------------------------------------------------------------
# Catalog + seed
# ---------------------------------------------------------------------
def test_catalog_is_valid():
    assert validate_catalog() == []
    assert len(INGREDIENTS) == 28 and len(PRODUCTS) == 33


def test_seed_loads_everything_and_is_idempotent():
    first = seed()
    brand_count = len(unique_eligible_products())
    assert first["products_new"] == 33 and first["ingredients_new"] >= 28
    assert first["branded_new"] == brand_count

    db = _TestSessionLocal()
    assert db.query(Product).count() == 33 + brand_count
    assert db.query(Ingredient).count() >= 28
    cleanser = db.query(Product).filter_by(name="Salicylic Acid Foaming Cleanser").one()
    assert {pi.ingredient.name for pi in cleanser.ingredients} == {"Salicylic Acid", "Zinc PCA", "Glycerin"}
    assert "How to use:" in cleanser.description and "Caution:" in cleanser.description
    assert cleanser.is_sample_data is True and cleanser.source
    links = db.query(ProductIngredient).count()
    db.close()

    second = seed()
    assert second["products_new"] == 0 and second["ingredients_new"] == 0 and second["branded_new"] == 0
    db = _TestSessionLocal()
    assert db.query(Product).count() == 33 + brand_count
    assert db.query(ProductIngredient).count() == links  # no duplicate links
    db.close()


def test_seed_removes_legacy_demo_products_unless_in_use():
    db = _TestSessionLocal()
    user = User(email="r@example.com")
    db.add(user)
    unused = Product(name="Old A", brand="SampleBrand", is_sample_data=True)
    used = Product(name="Old B", brand="SampleBrand", is_sample_data=True)
    db.add_all([unused, used])
    db.flush()
    routine = Routine(user_id=user.id, routine_type=RoutineType.morning)
    db.add(routine)
    db.flush()
    db.add(RoutineItem(routine_id=routine.id, product_id=used.id, step_order=1))
    db.commit()
    db.close()

    assert seed_catalog_counts()["legacy_removed"] == 1
    db = _TestSessionLocal()
    assert db.query(Product).filter_by(name="Old A").first() is None
    assert db.query(Product).filter_by(name="Old B").first() is not None
    db.close()


def seed_catalog_counts() -> dict:
    return seed()


# ---------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------
def test_requires_auth_and_profile():
    assert client.get("/api/v1/recommendations").status_code == 401
    t = token()
    r = recs(t)
    assert r.status_code == 404 and "skin assessment" in r.json()["detail"].lower()


def test_oily_acne_profile_gets_matching_routine_with_db_ids():
    seed()
    t = token()
    set_profile(t, skin_type="oily", concerns=["acne", "oiliness"])
    r = recs(t)
    assert r.status_code == 200, r.text
    body = r.json()

    assert body["skin_type"] == "oily" and body["matches"]
    by_name = {p["name"]: p for p in PRODUCTS}
    for m in body["matches"]:
        if m["is_sample_data"]:
            assert "oily" in by_name[m["name"]]["skin_types"]
        assert m["product_id"] is not None  # seeded -> real DB id
        assert m["match_reasons"]
    morning = {p["category"] for p in body["routine"]["morning"]}
    assert {"cleanser", "moisturizer", "sunscreen"} <= morning
    assert body["disclaimer"]


def test_product_ids_are_null_when_catalog_not_seeded():
    t = token()
    set_profile(t, skin_type="dry", concerns=["dryness"])
    body = recs(t).json()
    assert body["matches"] and all(m["product_id"] is None for m in body["matches"])


def test_sensitivity_hides_actives_and_fragrance():
    seed()
    t = token()
    set_profile(t, skin_type="combination", concerns=["sensitivity", "redness"])
    body = recs(t).json()
    assert body["matches"]
    assert not (ingredients_of(body) & (ACTIVE_INGREDIENTS | {"Fragrance"}))
    assert any("sensitivity" in n.lower() for n in body["notes"])


def test_pregnancy_caution_hides_listed_actives():
    seed()
    t = token()
    set_profile(t, skin_type="oily", concerns=["acne", "texture"])
    normal = recs(t).json()
    assert ingredients_of(normal) & PREGNANCY_CAUTION_INGREDIENTS  # there is something to hide

    safe = recs(t, pregnant_or_trying=True).json()
    assert not (ingredients_of(safe) & PREGNANCY_CAUTION_INGREDIENTS)
    assert any("pregnan" in n.lower() for n in safe["notes"])


def test_avoided_ingredients_are_excluded():
    seed()
    t = token()
    set_profile(t, skin_type="oily", concerns=["oiliness"], avoid_ingredients=["Niacinamide"])
    body = recs(t).json()
    assert body["matches"] and "Niacinamide" not in ingredients_of(body)


def test_unsure_skin_type_falls_back_to_balanced_and_says_so():
    seed()
    t = token()
    set_profile(t, skin_type="unsure", concerns=["dullness"])
    body = recs(t).json()
    assert body["skin_type"] == "balanced"
    assert any("not sure" in n for n in body["notes"])


def test_recommendations_are_per_user():
    seed()
    a, b = token("a@example.com"), token("b@example.com")
    set_profile(a, skin_type="dry", concerns=["dryness"])
    assert recs(b).status_code == 404  # b has no profile; a's does not leak


# ---------------------------------------------------------------------
# Agent tool uses the same matcher
# ---------------------------------------------------------------------
def test_agent_tool_returns_recommendations_and_respects_profile():
    seed()
    t = token()
    set_profile(t, skin_type="oily", concerns=["acne"], avoid_ingredients=["Niacinamide"])
    db = _TestSessionLocal()
    user = db.query(User).filter_by(email="a@example.com").one()
    ctx = ToolContext(db=db, user=user)

    out = run_tool(ctx, "get_product_recommendations", {})
    assert out["skin_type"] == "oily" and out["morning_routine"]
    assert "Niacinamide 5% Serum" not in out["other_matches"]
    assert all(p["name"] != "Niacinamide 5% Serum" for p in out["morning_routine"])

    # no profile -> a clear error the model can relay, not a crash
    other = User(email="np@example.com")
    db.add(other)
    db.commit()
    err = run_tool(ToolContext(db=db, user=other), "get_product_recommendations", {})
    assert "error" in err
    db.close()


def test_agent_profile_tools_respect_consent_off():
    t = token()
    set_profile(t, skin_type="oily", concerns=["acne"])
    db = _TestSessionLocal()
    user = db.query(User).filter_by(email="a@example.com").one()
    ctx = ToolContext(db=db, user=user, use_profile=False)

    profile = run_tool(ctx, "get_my_profile", {})
    recs_out = run_tool(ctx, "get_product_recommendations", {})
    assert profile.get("consent") is False and "skin_type" not in profile
    assert recs_out.get("consent") is False and "morning_routine" not in recs_out
    db.close()
