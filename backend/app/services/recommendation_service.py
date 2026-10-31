"""
Personalised product recommendations from the user's saved skin profile.

Two sources, brand products first:
  1. Brand products (DermaCare catalog, via services/branded_catalog.py) -
     real brands, eligible records only, with explicit ingredient_status
     and warnings because most ingredient data is incomplete.
  2. Generic sample products (knowledge_base/skincare_catalog.py) - used
     only to fill a routine step / category the brand products cannot.

This is educational matching, not medical advice. The matchers are
conservative heuristics, not guarantees, and the response says so.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.database.models import Product, User
from app.knowledge_base.skincare_catalog import BRAND as GENERIC_BRAND, build_basic_routine
from app.schemas.catalog_schema import (
    RecommendationResponse,
    RecommendedProduct,
    RoutineSuggestion,
)
from app.services import branded_catalog as bc

DISCLAIMER = (
    "These are educational suggestions matched to your saved preferences. They are not medical "
    "advice or a diagnosis, and no results are guaranteed. Brand listings come from the brands' "
    "official pages and most ingredient lists are incomplete - always read the current pack, patch "
    "test new products, and ask a doctor or pharmacist if you are pregnant, have a skin condition, "
    "or use prescription treatments."
)

MORNING_STEPS = ["cleanser", "serum", "moisturizer", "sunscreen"]
EVENING_STEPS = ["cleanser", "serum", "moisturizer"]


class NoProfileError(Exception):
    """The user has not saved a skin profile yet."""


def _brand_product(m: bc.Match, ids: dict[tuple[str, str], int]) -> RecommendedProduct:
    p = m.product
    return RecommendedProduct(
        product_id=ids.get((p["brand"], p["product_name"])),
        name=p["product_name"],
        brand=p["brand"],
        category=p["category"],
        usage_time=None,
        description=f"{p['brand']} {p['category'].replace('_', ' ')}",
        uses=None,
        how_to_use=bc.how_to_use(p),
        cautions=None,
        ingredients=list(p.get("full_ingredients_inci") or p.get("ingredient_highlights") or []),
        ingredient_status=m.status,
        warnings=m.warnings,
        is_sample_data=False,
        source_url=p["source_url"],
        score=m.score,
        match_reasons=m.reasons,
    )


def _generic_product(p: dict, ids: dict[tuple[str, str], int]) -> RecommendedProduct:
    return RecommendedProduct(
        product_id=ids.get((GENERIC_BRAND, p["name"])),
        name=p["name"],
        brand=GENERIC_BRAND,
        category=p["category"],
        usage_time=p["usage_time"],
        description=p["description"],
        uses=p["uses"],
        how_to_use=p["how_to_use"],
        cautions=p.get("cautions"),
        ingredients=p["ingredients"],
        ingredient_status="sample",
        warnings=["Generic sample product, not a real product listing."],
        is_sample_data=True,
        source_url=None,
        score=p["score"],
        match_reasons=p["match_reasons"],
    )


def build_recommendations(db: Session, user: User, pregnant_or_trying: bool = False) -> RecommendationResponse:
    profile = user.skin_profile
    if profile is None:
        raise NoProfileError()

    notes: list[str] = []
    skin_type = profile.skin_type.value
    if skin_type == "unsure":
        skin_type = "balanced"
        notes.append("Your skin type is set to 'not sure', so results are shown for balanced skin.")
    concerns = list(profile.concerns or [])
    avoid = list(profile.avoid_ingredients or [])

    if "sensitivity" in concerns:
        notes.append("Because you listed sensitivity, products with strong actives or fragrance are hidden.")
    if pregnant_or_trying:
        notes.append("Pregnancy caution is on: products with retinoids, acids and similar actives are hidden.")
    if avoid:
        notes.append("Products containing your avoided ingredients are hidden: " + ", ".join(avoid) + ".")
    if "sensitivity" in concerns or pregnant_or_trying or avoid:
        notes.append(
            "Only products with a full ingredient list can be screened for these settings, so brand products "
            "without one are hidden. This is a data limit, not a statement that they are unsafe."
        )

    branded_all = bc.recommend(
        skin_type=skin_type, concerns=concerns, avoid=avoid, pregnant_or_trying=pregnant_or_trying
    )
    branded_shown = bc.display_matches(branded_all)

    generic = build_basic_routine(
        {
            "skin_type": skin_type,
            "concerns": concerns,
            "pregnant_or_trying": pregnant_or_trying,
            "excluded_ingredients": avoid,
        }
    )

    # Routine steps: a brand product when one fits, else a generic one.
    def generic_pick(slot_items: list[dict], category: str) -> dict | None:
        return next((g for g in slot_items if g["category"] == category), None)

    morning: list[tuple[str, object]] = []
    evening: list[tuple[str, object]] = []
    for steps, generic_items, target, slot in (
        (MORNING_STEPS, generic["morning"], morning, "morning"),
        (EVENING_STEPS, generic["evening"], evening, "evening"),
    ):
        for category in steps:
            b = bc.routine_pick(branded_all, category, slot)
            if b is not None:
                target.append(("brand", b))
                continue
            g = generic_pick(generic_items, category)
            if g is not None:
                target.append(("generic", g))

    # Other matches: brand products, plus generic ones only for categories
    # with no brand product to show.
    shown_categories = {m.product["category"] for m in branded_shown}
    generic_extra = [g for g in generic["all_matches"] if g["category"] not in shown_categories]

    # Map to database ids so the UI can link to / create routines from them.
    names = {m.product["product_name"] for m in branded_all}
    names |= {g["name"] for g in generic["all_matches"]}
    ids = {
        (row.brand, row.name): row.id
        for row in db.query(Product).filter(Product.name.in_(names)).all()
    }

    def convert(kind: str, item) -> RecommendedProduct:
        return _brand_product(item, ids) if kind == "brand" else _generic_product(item, ids)

    matches = [convert("brand", m) for m in branded_shown] + [convert("generic", g) for g in generic_extra]

    if any(not m.is_sample_data for m in matches):
        notes.append(
            "Brand products come from official brand pages. Only some have a verified full ingredient "
            "list - each card says which."
        )
    if any(m.is_sample_data for m in matches):
        notes.append("Generic sample products fill in where no matching brand product was found.")

    return RecommendationResponse(
        skin_type=skin_type,
        concerns=concerns,
        matches=matches,
        routine=RoutineSuggestion(
            morning=[convert(k, i) for k, i in morning],
            evening=[convert(k, i) for k, i in evening],
        ),
        notes=notes,
        disclaimer=DISCLAIMER,
    )
