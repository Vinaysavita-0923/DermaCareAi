"""
Loads the uploaded searchable product catalogue
(dermacare_products_searchable_categories.csv, 1472 rows across the 9
`product_type` categories in dermacare_product_category_summary.csv) into
the same `products` table the rest of the app already reads from.

This is a separate, much larger catalogue than
app/knowledge_base/skincare_catalog.py and dermacare_products_improved.json
(used by the assessment/recommendation engine) and does NOT touch either -
it only adds rows the catalog search/browse feature (GET /api/v1/products)
can find. Ingredients are kept as the raw `ingredients_text` column rather
than exploded into Ingredient/ProductIngredient rows, so this does not
pollute the curated Ingredient table the recommendation engine relies on
for precaution text.

Everything loaded here is marked is_sample_data=False with a `source` that
says plainly the ingredient data is unverified and not clinically
validated (matches the CSV's own verification_status / medical_claims_status
columns) - per the project brief, never invent availability, price, or
medical effectiveness, and never claim unverified data is verified.

Safe to re-run: existing rows (matched by name + brand) are updated in
place, nothing is duplicated.

    python -m scripts.seed_dermacare_catalog [path/to/csv]

Defaults to the sibling CSV this project was built against if no path is
given: C:\\Users\\ABC\\Downloads\\dermacare_products_searchable_categories.csv
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy.orm import Session  # noqa: E402

from app.database.connection import SessionLocal  # noqa: E402
from app.database.models import Product  # noqa: E402

DEFAULT_CSV_PATH = Path(r"C:\Users\ABC\Downloads\dermacare_products_searchable_categories.csv")

SOURCE_NOTE = (
    "Uploaded skincare product catalogue (dermacare_products_searchable_categories.csv). "
    "Ingredient data is unverified source data and not clinically validated."
)


def _float_or_none(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _int_or_none(value: str | None) -> int | None:
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _bool_or_none(value: str | None) -> bool | None:
    if value is None or value.strip() == "":
        return None
    return value.strip().lower() == "true"


def _description_for(row: dict) -> str:
    parts = [f"{row['product_type']} by {row['brand']}" if row.get("brand") else row["product_type"]]
    count = row.get("ingredient_count")
    if count:
        parts.append(f"{count} listed ingredients.")
    return " ".join(parts)


def seed(csv_path: Path) -> tuple[int, int]:
    created = 0
    updated = 0
    db: Session = SessionLocal()
    try:
        with csv_path.open(encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            for i, row in enumerate(reader, start=1):
                name = (row.get("name") or "").strip()
                brand = (row.get("brand") or "").strip() or None
                # A couple of rows in the source CSV carry "#NAME?" - an
                # Excel formula-error artifact, not a real product name.
                # Skip rather than invent a replacement name.
                if not name or name == "#NAME?":
                    continue

                product = db.query(Product).filter_by(name=name, brand=brand).first()
                if product is None:
                    product = Product(name=name, brand=brand)
                    db.add(product)
                    created += 1
                else:
                    updated += 1

                product.category = (row.get("product_type") or "").strip() or None
                product.description = _description_for(row)
                product.is_sample_data = False
                product.source = SOURCE_NOTE
                product.rating = _float_or_none(row.get("rating"))
                product.ingredients_text = (row.get("ingredients_text") or "").strip() or None
                product.ingredients_list = (row.get("ingredients_list") or "").strip() or None
                product.ingredient_count = _int_or_none(row.get("ingredient_count"))
                product.suitable_dry = _bool_or_none(row.get("suitable_dry"))
                product.suitable_normal = _bool_or_none(row.get("suitable_normal"))
                product.suitable_oily = _bool_or_none(row.get("suitable_oily"))
                product.suitable_combination = _bool_or_none(row.get("suitable_combination"))
                product.suitable_sensitive = _bool_or_none(row.get("suitable_sensitive"))

                if i % 200 == 0:
                    db.commit()

        db.commit()
    finally:
        db.close()

    return created, updated


if __name__ == "__main__":
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_CSV_PATH
    if not path.exists():
        print(f"CSV not found: {path}")
        sys.exit(1)

    created, updated = seed(path)
    print(f"Seeded dermacare catalog from {path}: {created} created, {updated} updated.")
