"""
DermaCare AI — branded skincare catalog + transparent assessment matcher.

DATA / SAFETY PRINCIPLES
- Catalog listings are not proof of current availability or a current individual product page.
- Candidate records requiring product-page verification are excluded by default.
- Ingredient highlights are not a complete ingredient list.
- Safety-sensitive screening (sensitivity, pregnancy/trying to conceive, and
  user-excluded ingredients) is withheld when a full INCI list is unavailable.
- This is a transparent ranking heuristic, not a clinical decision engine.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DATA_PATH = Path(__file__).with_name("dermacare_products_improved.json")

ELIGIBLE_STATUSES = {
    "official_catalog_listing_seen",
    "official_product_page_ingredient_list_seen",
}
CANDIDATE_STATUS = "brand_page_candidate_requires_product_page_verification"

SENSITIVITY_FLAG_TERMS = (
    "retinol", "retinal", "retinoid", "glycolic acid",
    "lactic acid", "salicylic acid", "benzoyl peroxide",
)
RETINOID_TERMS = ("retinol", "retinal", "retinoid")


def load_catalog(path: str | Path = DATA_PATH) -> list[dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    products = payload["products"]
    validate_catalog(products)
    return products


def validate_catalog(products: list[dict[str, Any]]) -> None:
    required = {
        "id", "brand", "product_name", "category", "skin_types", "concerns",
        "ingredient_highlights", "full_ingredients_inci", "source_url",
        "verification_status", "source_note",
    }
    allowed_statuses = ELIGIBLE_STATUSES | {CANDIDATE_STATUS}
    ids: set[str] = set()

    for p in products:
        missing = required - p.keys()
        if missing:
            raise ValueError(
                f"{p.get('product_name', '<unknown>')} missing {sorted(missing)}"
            )
        if p["id"] in ids:
            raise ValueError(f"Duplicate product id: {p['id']}")
        ids.add(p["id"])

        if (
            not p["brand"]
            or not p["product_name"]
            or not str(p["source_url"]).startswith("https://")
        ):
            raise ValueError(f"Invalid core fields for {p['id']}")
        if p["verification_status"] not in allowed_statuses:
            raise ValueError(
                f"Unexpected verification status: {p['verification_status']}"
            )
        if p["full_ingredients_inci"] is not None and not isinstance(
            p["full_ingredients_inci"], list
        ):
            raise ValueError(f"full_ingredients_inci must be a list or null: {p['id']}")
        if p["verification_status"] == "official_product_page_ingredient_list_seen":
            if not p["full_ingredients_inci"]:
                raise ValueError(
                    f"{p['id']} claims product-page ingredient verification "
                    "but has no full INCI list"
                )


def _ingredient_text(product: dict[str, Any]) -> str:
    highlights = product.get("ingredient_highlights") or []
    inci = product.get("full_ingredients_inci") or []
    return " ".join(str(x) for x in highlights + inci).casefold()


def _has_full_inci(product: dict[str, Any]) -> bool:
    return bool(product.get("full_ingredients_inci"))


def score_product(
    product: dict[str, Any],
    *,
    skin_type: str,
    concerns: list[str] | None = None,
    sensitive: bool = False,
    excluded_ingredients: list[str] | None = None,
    pregnant_or_trying: bool = False,
    include_unverified: bool = False,
) -> dict[str, Any] | None:
    """
    Transparent ranking heuristic, not a clinical decision engine.

    If include_unverified=True, candidate records may be returned for internal
    catalog review only. They are explicitly labelled unverified.
    """
    status = product["verification_status"]
    if status not in ELIGIBLE_STATUSES:
        if not (include_unverified and status == CANDIDATE_STATUS):
            return None

    has_full_inci = _has_full_inci(product)
    excluded = [x.strip().casefold() for x in (excluded_ingredients or []) if x.strip()]

    # Never imply that an ingredient is absent from an incomplete ingredient list.
    if (sensitive or pregnant_or_trying or excluded) and not has_full_inci:
        return None

    ingredient_text = _ingredient_text(product)

    if any(term in ingredient_text for term in excluded):
        return None

    if sensitive:
        if product["category"].casefold() in {"exfoliant", "spot_treatment"}:
            return None
        if any(term in ingredient_text for term in SENSITIVITY_FLAG_TERMS):
            return None

    if pregnant_or_trying and any(
        term in ingredient_text for term in RETINOID_TERMS
    ):
        return None

    score = 0
    reasons: list[str] = []
    product_skin_types = {
        str(x).casefold() for x in product.get("skin_types", [])
    }

    if "all" in product_skin_types or skin_type.casefold() in product_skin_types:
        score += 3
        reasons.append("skin type tag match (catalog metadata)")
    elif product_skin_types:
        score -= 2

    requested_concerns = {str(x).casefold() for x in (concerns or [])}
    product_concerns = {
        str(x).casefold() for x in product.get("concerns", [])
    }
    matched = requested_concerns.intersection(product_concerns)
    score += 2 * len(matched)
    if matched:
        reasons.append("concern tag match: " + ", ".join(sorted(matched)))

    if not has_full_inci:
        ingredient_note = (
            "ingredient screening incomplete: full INCI unavailable; "
            "do not infer ingredient absence or safety"
        )
    else:
        ingredient_note = (
            "full INCI recorded in catalog; confirm current pack because "
            "formulations can vary"
        )

    is_candidate = status == CANDIDATE_STATUS
    verification_note = (
        "UNVERIFIED CANDIDATE — internal review only; not a confirmed product listing"
        if is_candidate
        else (
            "official catalog listing seen; individual product page/current "
            "availability not necessarily verified"
            if status == "official_catalog_listing_seen"
            else "official product-page ingredient list recorded; current pack still needs checking"
        )
    )

    return {
        "product": product,
        "score": score,
        "match_reasons": reasons,
        "ingredient_data_note": ingredient_note,
        "verification_note": verification_note,
        "recommendation_eligible": not is_candidate,
        "disclaimer": (
            "Informational matching only, not medical advice. Check the current "
            "packaging and consult a qualified clinician for pregnancy, allergy, "
            "persistent irritation, or medical skin concerns."
        ),
    }


def recommend(
    *,
    skin_type: str,
    concerns: list[str] | None = None,
    sensitive: bool = False,
    excluded_ingredients: list[str] | None = None,
    pregnant_or_trying: bool = False,
    categories: list[str] | None = None,
    limit: int = 10,
    include_unverified: bool = False,
    catalog: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Rank catalog matches; unverified candidates are opt-in and labelled."""
    products = catalog if catalog is not None else load_catalog()
    wanted_categories = {x.casefold() for x in (categories or [])}
    ranked = []

    for product in products:
        if wanted_categories and product["category"].casefold() not in wanted_categories:
            continue
        result = score_product(
            product,
            skin_type=skin_type,
            concerns=concerns,
            sensitive=sensitive,
            excluded_ingredients=excluded_ingredients,
            pregnant_or_trying=pregnant_or_trying,
            include_unverified=include_unverified,
        )
        if result is not None:
            ranked.append(result)

    ranked.sort(
        key=lambda item: (
            item["recommendation_eligible"],
            item["score"],
            item["product"]["brand"],
        ),
        reverse=True,
    )
    return ranked[:max(0, limit)]


def catalog_stats(catalog: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    products = catalog if catalog is not None else load_catalog()
    status_counts: dict[str, int] = {}
    for product in products:
        status = product["verification_status"]
        status_counts[status] = status_counts.get(status, 0) + 1

    full_inci = sum(_has_full_inci(p) for p in products)
    no_ingredient_data = sum(
        not (p.get("ingredient_highlights") or [])
        and not (p.get("full_ingredients_inci") or [])
        for p in products
    )
    highlights_only = sum(
        bool(p.get("ingredient_highlights"))
        and not _has_full_inci(p)
        for p in products
    )

    return {
        "total_records": len(products),
        "unique_brands": len({p["brand"] for p in products}),
        "verification_status_counts": status_counts,
        "eligible_for_default_recommendations": sum(
            p["verification_status"] in ELIGIBLE_STATUSES for p in products
        ),
        "records_with_full_inci": full_inci,
        "records_without_full_inci": len(products) - full_inci,
        "records_with_highlights_only": highlights_only,
        "records_with_no_ingredient_data": no_ingredient_data,
    }


if __name__ == "__main__":
    catalog = load_catalog()
    print("DermaCare AI catalog validation passed.")
    print(json.dumps(catalog_stats(catalog), indent=2))
    print("\nSample recommendations for oily skin + acne:")
    results = recommend(
        skin_type="oily",
        concerns=["acne", "oiliness"],
        categories=["cleanser", "serum", "moisturizer", "sunscreen"],
        limit=8,
        catalog=catalog,
    )
    for item in results:
        product = item["product"]
        print(
            f"- {product['brand']} — {product['product_name']} "
            f"(score={item['score']}; {item['ingredient_data_note']})"
        )
