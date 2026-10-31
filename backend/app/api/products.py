"""
GET /api/v1/products         — search the product catalog
GET /api/v1/products/{id}    — one product with its ingredients

Read-only. Products are global catalog data, not per-user data, so
there is no ownership check here — any authenticated user can browse
the same catalog. Every product always reports `is_sample_data` and
`source`, so the client can never mistake demo content for a verified
claim (per the project brief: no invented availability, prices, or
medical effectiveness).
"""
from __future__ import annotations

from sqlalchemy import func

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, selectinload

from app.core.security import get_current_user
from app.database.connection import get_db
from app.database.models import Product, User
from app.schemas.catalog_schema import (
    IngredientOut,
    ProductCategoryOut,
    ProductCountOut,
    ProductDetailOut,
    ProductOut,
)

router = APIRouter(prefix="/products", tags=["products"])

# The 9 categories the product search/browse UI is built around (matches
# `product_type` in the uploaded dermacare catalogue, see
# dermacare_product_category_summary.csv). Always returned in this order,
# with count 0 for a category nothing is currently seeded under.
CANONICAL_CATEGORIES = [
    "Sunscreen",
    "Moisturizer",
    "Cleanser",
    "Toner & Essence",
    "Serum & Treatment",
    "Face Mask",
    "Eye Care",
    "Exfoliator & Peel",
    "Spot Treatment",
]


def _filtered_query(db: Session, q: str | None, category: str | None):
    query = db.query(Product)
    if q:
        like = f"%{q.strip()}%"
        query = query.filter(
            Product.name.ilike(like)
            | Product.brand.ilike(like)
            | Product.ingredients_text.ilike(like)
        )
    if category:
        query = query.filter(func.lower(Product.category) == category.strip().lower())
    return query


@router.get("/categories", response_model=list[ProductCategoryOut])
def list_product_categories(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ProductCategoryOut]:
    rows = (
        db.query(Product.category, func.count(Product.id))
        .filter(Product.category.isnot(None))
        .group_by(Product.category)
        .all()
    )
    counts_by_lower: dict[str, int] = {}
    for category, count in rows:
        if not category:
            continue
        key = category.lower()
        counts_by_lower[key] = counts_by_lower.get(key, 0) + count
    return [
        ProductCategoryOut(category=name, count=counts_by_lower.get(name.lower(), 0))
        for name in CANONICAL_CATEGORIES
    ]


@router.get("/count", response_model=ProductCountOut)
def count_products(
    q: str | None = Query(default=None, description="Search product, brand or ingredients"),
    category: str | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProductCountOut:
    return ProductCountOut(count=_filtered_query(db, q, category).count())


@router.get("", response_model=list[ProductOut])
def search_products(
    q: str | None = Query(default=None, description="Search product, brand or ingredients"),
    category: str | None = Query(default=None),
    limit: int = Query(default=60, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Product]:
    query = _filtered_query(db, q, category)
    return query.order_by(Product.name.asc()).offset(offset).limit(limit).all()


@router.get("/{product_id}", response_model=ProductDetailOut)
def get_product(
    product_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Product:
    product = (
        db.query(Product)
        .options(selectinload(Product.ingredients))
        .filter(Product.id == product_id)
        .first()
    )
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found.")

    # Build the response explicitly rather than mutating product.ingredients
    # in place — that attribute is a live SQLAlchemy relationship
    # (list[ProductIngredient]) and reassigning it on the actual ORM
    # instance would corrupt the session's tracking of this object.
    return ProductDetailOut(
        id=product.id,
        name=product.name,
        brand=product.brand,
        category=product.category,
        description=product.description,
        is_sample_data=product.is_sample_data,
        source=product.source,
        rating=product.rating,
        ingredients=[
            IngredientOut.model_validate(pi.ingredient) for pi in product.ingredients
        ],
        ingredients_text=product.ingredients_text,
        ingredients_list=product.ingredients_list,
        ingredient_count=product.ingredient_count,
        suitable_dry=product.suitable_dry,
        suitable_normal=product.suitable_normal,
        suitable_oily=product.suitable_oily,
        suitable_combination=product.suitable_combination,
        suitable_sensitive=product.suitable_sensitive,
    )
