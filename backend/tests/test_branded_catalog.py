"""
Tests for the DermaCare brand-catalog layer: eligibility, de-duplication,
ingredient status, the safety filters, routine placement, and the DB seed.

They verify the rules behave as written against this dataset. They do not
prove any product is suitable for a real person.
"""
from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.connection import Base, get_db
from app.database.models import Ingredient, Product
from app.knowledge_base import dermacare_catalog_improved as dc
from app.main import app
from app.services import branded_catalog as bc
from scripts.seed_demo_products import seed_catalog

TEST_DB_PATH = "test_branded.db"
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


def token(email="a@example.com") -> str:
    client.post("/api/v1/auth/register", json={"full_name": "A", "email": email, "password": "StrongPass1"})
    return client.post("/api/v1/auth/login", json={"email": email, "password": "StrongPass1"}).json()["access_token"]


def auth(t):
    return {"Authorization": f"Bearer {t}"}


def seed():
    db = _TestSessionLocal()
    try:
        return seed_catalog(db)
    finally:
        db.close()


def match(**kw):
    base = dict(skin_type="oily", concerns=["acne", "oiliness"], avoid=[], pregnant_or_trying=False)
    base.update(kw)
    return bc.recommend(**base)


# ---------------------------------------------------------------------
# Eligibility + de-duplication
# ---------------------------------------------------------------------
def test_only_eligible_records_are_used():
    for p in bc.unique_eligible_products():
        assert p["verification_status"] in dc.ELIGIBLE_STATUSES
        assert p["category"] in bc.RECOMMENDABLE_CATEGORIES


def test_size_variants_collapse_to_one_product():
    names = [p["product_name"] for p in bc.unique_eligible_products() if p["brand"] == "Cetaphil"]
    assert len([n for n in names if n.startswith("Gentle Skin Cleanser")]) == 1
    keys = [(p["brand"], bc.norm_name(p["product_name"])) for p in bc.unique_eligible_products()]
    assert len(keys) == len(set(keys))


def test_ingredient_status_classification():
    by = {p["product_name"]: p for p in bc.unique_eligible_products()}
    assert bc.ingredient_status(by["Deep Clean Facial Cleanser"]) == "verified"
    assert bc.ingredient_status(by["Niacinamide 10% Serum"]) == "partial"
    assert bc.ingredient_status(by["SPF 50 Sunscreen"]) == "unverified"


# ---------------------------------------------------------------------
# Safety filters
# ---------------------------------------------------------------------
def test_pregnancy_caution_hides_every_retinoid_and_acid_including_by_name():
    # Oily + acne: the only full-INCI products here contain salicylic acid -> nothing left.
    assert match(pregnant_or_trying=True) == []
    r = match(skin_type="dry", concerns=["dryness"], pregnant_or_trying=True)
    assert r  # the full-INCI Cetaphil cleanser has no retinoid/acid
    for m in r:
        assert not bc._has_any(bc.product_text(m.product), bc.PREGNANCY_TERMS), m.product["product_name"]


def test_sensitive_skin_hides_actives_and_fragrance():
    r = match(skin_type="dry", concerns=["sensitivity"])
    assert r
    for m in r:
        assert not bc._has_any(bc.product_text(m.product), bc.SENSITIVE_TERMS), m.product["product_name"]


def test_avoided_ingredient_is_excluded_when_listed_in_full_ingredients():
    with_fragrance = [m for m in match() if "fragrance" in bc.product_text(m.product)]
    assert any(m.product["product_name"] == "Deep Clean Facial Cleanser" for m in with_fragrance)
    after = match(avoid=["Fragrance"])
    assert not [m for m in after if "fragrance" in bc.product_text(m.product)]


def test_without_a_full_ingredient_list_products_are_withheld_when_a_safety_setting_is_on():
    # Normally shown, with an honest warning...
    shown = match()
    assert any(m.status == "unverified" for m in shown) and any(m.status == "partial" for m in shown)
    unverified = next(m for m in shown if m.status == "unverified")
    assert any("not verified" in w for w in unverified.warnings)
    partial = next(m for m in shown if m.status == "partial")
    assert any("Only key ingredients" in w for w in partial.warnings)
    # ...but with any safety setting on, only full-INCI products can be screened.
    for kw in (
        dict(avoid=["fragrance"]),
        dict(pregnant_or_trying=True),
        dict(concerns=["sensitivity"], skin_type="dry"),
        dict(skin_type="dry", concerns=["dryness"], avoid=["glycerin"]),
    ):
        assert all(m.status == "verified" for m in match(**kw)), kw


def test_skin_type_must_fit():
    for m in match(skin_type="dry", concerns=["dryness"]):
        sts = {x.casefold() for x in m.product["skin_types"]}
        assert "all" in sts or "dry" in sts


# ---------------------------------------------------------------------
# Routine placement
# ---------------------------------------------------------------------
def test_routine_never_auto_places_retinoids_and_respects_day_night():
    ranked = match(skin_type="balanced", concerns=["texture", "dullness", "fine_lines"][:2])
    for slot, cats in (("morning", ["cleanser", "serum", "moisturizer", "sunscreen"]), ("evening", ["cleanser", "serum", "moisturizer"])):
        for cat in cats:
            pick = bc.routine_pick(ranked, cat, slot)
            if pick is None:
                continue
            assert not bc.has_retinoid(pick.product)
            name = pick.product["product_name"]
            if slot == "morning":
                assert not bc._NIGHT_RE.search(name), name
            else:
                assert not bc._DAY_RE.search(name), name


def test_other_matches_need_a_concern_match_beyond_the_basics():
    for m in bc.display_matches(match()):
        if m.product["category"] not in bc.BASIC_CATEGORIES:
            assert any(r.startswith("concern tag match") for r in m.reasons), m.product["product_name"]


def test_time_ok_rules():
    assert not bc.time_ok("Healthy Radiance Brightening Night Cream", "morning")
    assert bc.time_ok("Healthy Radiance Brightening Night Cream", "evening")
    assert not bc.time_ok("Daily Facial Moisturizer SPF 15", "evening")
    assert not bc.time_ok("Light Fluid SPF 50 Sunscreen", "evening")
    assert bc.time_ok("Light Fluid SPF 50 Sunscreen", "morning")


# ---------------------------------------------------------------------
# DB seed
# ---------------------------------------------------------------------
def test_seed_loads_brand_products_not_candidates_and_no_prices():
    seed()
    db = _TestSessionLocal()
    brands = db.query(Product).filter(Product.brand != "Sample (generic)").all()
    assert len(brands) == len(bc.unique_eligible_products())
    assert all(p.is_sample_data is False for p in brands)
    names = {p.name for p in brands}
    assert "PHA 3% Toner" not in names  # a brand_page_candidate (unverified)
    p = db.query(Product).filter_by(name="Niacinamide 10% Serum", brand="Minimalist").one()
    assert "Always check the current pack" in p.description and "checked" in p.source
    assert "price" not in p.description.lower()
    db.close()


def test_seed_links_full_ingredient_lists_and_reuses_precaution_text():
    seed()
    db = _TestSessionLocal()
    cet = db.query(Product).filter_by(name="Gentle Skin Cleanser", brand="Cetaphil").one()
    assert len(cet.ingredients) == 10
    neu = db.query(Product).filter_by(name="Deep Clean Facial Cleanser", brand="Neutrogena").one()
    sal = next(pi.ingredient for pi in neu.ingredients if pi.ingredient.name == "Salicylic Acid")
    assert sal.precautions and "sunscreen" in sal.precautions.lower()  # our generic precaution text
    assert db.query(Ingredient).filter_by(name="Salicylic Acid").count() == 1  # no duplicate row
    db.close()


# ---------------------------------------------------------------------
# Endpoint: brand products first, generic fallback, honest labelling
# ---------------------------------------------------------------------
def set_profile(t, **body):
    assert client.put("/api/v1/profile", json=body, headers=auth(t)).status_code == 200


def test_endpoint_returns_brand_products_with_status_and_ids():
    seed()
    t = token()
    set_profile(t, skin_type="oily", concerns=["acne", "oiliness"])
    body = client.get("/api/v1/recommendations", headers=auth(t)).json()
    brand = [m for m in body["matches"] if not m["is_sample_data"]]
    assert brand and all(m["ingredient_status"] in {"verified", "partial", "unverified"} for m in brand)
    assert all(m["product_id"] is not None and m["source_url"] for m in brand)
    assert {"cleanser", "moisturizer"} <= {p["category"] for p in body["routine"]["morning"]}
    assert not any(bc.has_retinoid(next(x for x in bc.unique_eligible_products() if x["product_name"] == p["name"]))
                   for p in body["routine"]["morning"] + body["routine"]["evening"] if not p["is_sample_data"])
    assert "price" not in str(body).lower().replace("price_inr", "")


def test_endpoint_pregnancy_and_avoid_settings_apply_to_brand_products():
    seed()
    t = token()
    set_profile(t, skin_type="oily", concerns=["acne"], avoid_ingredients=["Fragrance"])
    body = client.get("/api/v1/recommendations", params={"pregnant_or_trying": True}, headers=auth(t)).json()
    for m in body["matches"] + body["routine"]["morning"] + body["routine"]["evening"]:
        if m["is_sample_data"]:
            continue
        assert m["ingredient_status"] == "verified"
        text = (m["name"] + " " + " ".join(m["ingredients"])).lower()
        assert "fragrance" not in text and not bc._has_any(text, bc.PREGNANCY_TERMS)
    assert any("full ingredient list" in n for n in body["notes"])


def test_generic_products_fill_in_when_no_brand_product_fits(monkeypatch):
    seed()
    monkeypatch.setattr("app.services.recommendation_service.bc.recommend", lambda **kw: [])
    t = token()
    set_profile(t, skin_type="oily", concerns=["acne"])
    body = client.get("/api/v1/recommendations", headers=auth(t)).json()
    assert body["matches"] and all(m["is_sample_data"] for m in body["matches"])
    assert body["routine"]["morning"] and all(m["is_sample_data"] for m in body["routine"]["morning"])
    assert any("Generic sample products fill in" in n for n in body["notes"])
