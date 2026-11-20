"""
Loads the catalogs into the database: ingredients, products, and the
product <-> ingredient links.

  * Generic sample archetypes (app/knowledge_base/skincare_catalog.py):
    is_sample_data=True, brand "Sample (generic)".
  * Brand products (dermacare_products.json): ONLY the eligible records
    (official listing/product page seen, size variants collapsed).
    Unverified candidates are never loaded. is_sample_data=False, and each
    `source` says whether the ingredient list was verified.

Nothing here carries prices or availability ("do not invent availability,
prices, or medical effectiveness").

This is NOT run automatically (not in tests, not on app startup) - run it
yourself when you want catalog data to browse locally:

    python -m scripts.seed_demo_products

Safe to re-run: existing rows are updated in place, nothing is duplicated.
The older 3-item "SampleBrand" demo products are removed if no routine
uses them.

The database has no separate columns for uses / how-to-use / cautions, so
those are written into the description text (see _product_description).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy.orm import Session  # noqa: E402

from app.database.connection import SessionLocal  # noqa: E402
from app.database.models import Ingredient, Product, ProductIngredient, RoutineItem  # noqa: E402
from app.knowledge_base.skincare_catalog import (  # noqa: E402
    BRAND,
    INGREDIENTS,
    PRODUCTS,
    SOURCE,
    validate_catalog,
)
from app.services.branded_catalog import (  # noqa: E402
    description_for as branded_description,
    source_text as branded_source,
    unique_eligible_products,
)

LEGACY_BRAND = "SampleBrand"


def _ingredient_description(item: dict) -> str:
    return f"{item['description']}\n\nCommonly used: {item['uses']}"


def _product_description(item: dict) -> str:
    parts = [item["description"], f"Uses: {item['uses']}", f"How to use: {item['how_to_use']}"]
    if item.get("cautions"):
        parts.append(f"Caution: {item['cautions']}")
    return "\n".join(parts)


def _ingredient_aliases(known: dict[str, Ingredient]) -> dict[str, str]:
    """Brand highlights ("Vitamin C", "Cica") -> the generic ingredient rows
    that carry our precaution text."""
    aliases = {name.casefold(): name for name in known}
    aliases.update(
        {
            "vitamin c": "Vitamin C (Ascorbic Acid)",
            "vitamin b5": "Panthenol (Vitamin B5)",
            "panthenol": "Panthenol (Vitamin B5)",
            "green tea": "Green Tea Extract",
            "tea tree": "Tea Tree Oil",
            "centella": "Centella Asiatica",
            "cica": "Centella Asiatica",
        }
    )
    return {k: v for k, v in aliases.items() if v in known}


def _seed_branded(db: Session, known: dict[str, Ingredient]) -> int:
    """Load the eligible, de-duplicated brand products (never the unverified
    candidates). Full INCI lists become ingredient links; for the rest only
    the highlights that match an ingredient we hold precaution text for."""
    aliases = _ingredient_aliases(known)
    created = 0
    for p in unique_eligible_products():
        product = db.query(Product).filter_by(name=p["product_name"], brand=p["brand"]).first()
        if product is None:
            product = Product(name=p["product_name"], brand=p["brand"])
            db.add(product)
            created += 1
        product.category = p["category"]
        product.description = branded_description(p)
        product.is_sample_data = False
        product.source = branded_source(p)
        db.flush()

        full = bool(p.get("full_ingredients_inci"))
        names = p["full_ingredients_inci"] if full else p.get("ingredient_highlights") or []
        linked = {pi.ingredient_id for pi in product.ingredients}
        for raw in names:
            canonical = aliases.get(raw.casefold())
            ing = known.get(canonical) if canonical else None
            if ing is None and full:  # INCI item we have no text for: keep the name only
                ing = db.query(Ingredient).filter_by(name=raw).first()
                if ing is None:
                    ing = Ingredient(name=raw, source="Name copied from the official product page ingredient list.")
                    db.add(ing)
                    db.flush()
                known[raw] = ing
            if ing is not None and ing.id not in linked:
                db.add(ProductIngredient(product_id=product.id, ingredient_id=ing.id))
                linked.add(ing.id)
    return created


def seed_catalog(db: Session) -> dict[str, int]:
    """Insert or update the whole catalog. Returns counts for reporting."""
    problems = validate_catalog()
    if problems:
        raise ValueError("Catalog is invalid:\n" + "\n".join(problems))

    counts = {"ingredients_new": 0, "products_new": 0, "legacy_removed": 0}

    name_to_ingredient: dict[str, Ingredient] = {}
    for item in INGREDIENTS:
        ing = db.query(Ingredient).filter_by(name=item["name"]).first()
        if ing is None:
            ing = Ingredient(name=item["name"])
            db.add(ing)
            counts["ingredients_new"] += 1
        ing.description = _ingredient_description(item)
        ing.precautions = item["precautions"]
        ing.source = SOURCE
        db.flush()
        name_to_ingredient[item["name"]] = ing

    for item in PRODUCTS:
        product = db.query(Product).filter_by(name=item["name"], brand=BRAND).first()
        if product is None:
            product = Product(name=item["name"], brand=BRAND)
            db.add(product)
            counts["products_new"] += 1
        product.category = item["category"]
        product.description = _product_description(item)
        product.is_sample_data = True
        product.source = SOURCE
        db.flush()

        linked = {pi.ingredient_id for pi in product.ingredients}
        for ing_name in item["ingredients"]:
            ing = name_to_ingredient[ing_name]
            if ing.id not in linked:
                db.add(ProductIngredient(product_id=product.id, ingredient_id=ing.id))
                linked.add(ing.id)

    counts["branded_new"] = _seed_branded(db, name_to_ingredient)

    # Retire the old 3-item demo set, but never one a user routine points at.
    for legacy in db.query(Product).filter_by(brand=LEGACY_BRAND, is_sample_data=True).all():
        if db.query(RoutineItem).filter_by(product_id=legacy.id).first():
            continue
        for pi in list(legacy.ingredients):
            db.delete(pi)
        db.delete(legacy)
        counts["legacy_removed"] += 1

    db.commit()
    return counts


def main() -> None:
    db = SessionLocal()
    try:
        c = seed_catalog(db)
        print(
            f"Seed complete. {len(PRODUCTS)} generic + {len(unique_eligible_products())} brand products "
            f"({c['products_new']} generic and {c['branded_new']} brand products newly added, "
            f"{c['ingredients_new']} ingredients added, {c['legacy_removed']} old demo products removed)."
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
