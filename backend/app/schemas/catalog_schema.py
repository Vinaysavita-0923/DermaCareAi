"""
Request/response shapes for products, ingredients, routines, and
reports.

Per the project brief: "Do not invent availability, prices, or medical
effectiveness." ProductOut always carries `is_sample_data` and `source`
so the client can never mistake demo content for a verified claim.
"""
from __future__ import annotations

import datetime

from pydantic import BaseModel, ConfigDict, field_validator

from app.database.models import RoutineType


# ---------------------------------------------------------------------
# Products / ingredients (read-only catalog)
# ---------------------------------------------------------------------
class IngredientOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None
    precautions: str | None
    source: str | None


class ProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    brand: str | None
    category: str | None
    description: str | None
    is_sample_data: bool
    source: str | None
    rating: float | None = None


class ProductDetailOut(ProductOut):
    ingredients: list[IngredientOut]
    ingredients_text: str | None = None
    ingredients_list: str | None = None
    ingredient_count: int | None = None
    suitable_dry: bool | None = None
    suitable_normal: bool | None = None
    suitable_oily: bool | None = None
    suitable_combination: bool | None = None
    suitable_sensitive: bool | None = None


class ProductCategoryOut(BaseModel):
    category: str
    count: int


class ProductCountOut(BaseModel):
    count: int


# ---------------------------------------------------------------------
# Routines (minimal CRUD — a prerequisite for routine-completion
# reports; see README "Phase 7 scope note")
# ---------------------------------------------------------------------
class RoutineItemCreate(BaseModel):
    product_id: int | None = None
    step_order: int = 0
    notes: str | None = None


class RoutineCreate(BaseModel):
    routine_type: RoutineType
    items: list[RoutineItemCreate] = []


class RoutineItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: int | None
    step_order: int
    notes: str | None


class RoutineOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    routine_type: RoutineType
    created_at: datetime.datetime
    items: list[RoutineItemOut]


class RoutineLogRequest(BaseModel):
    log_date: datetime.date
    completed: bool = True

    @field_validator("log_date")
    @classmethod
    def _not_future(cls, value: datetime.date) -> datetime.date:
        if value > datetime.date.today():
            raise ValueError("Log date cannot be in the future.")
        return value


class RoutineLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    routine_id: int
    log_date: datetime.date
    completed: bool


# ---------------------------------------------------------------------
# Recommendations (rule-based matching against the sample catalog)
# ---------------------------------------------------------------------
class RecommendedProduct(BaseModel):
    product_id: int | None  # None if the catalog has not been seeded into the DB
    name: str
    brand: str | None
    category: str
    usage_time: str | None  # morning | night | both; unknown for brand products
    description: str
    uses: str | None
    how_to_use: str | None
    cautions: str | None
    ingredients: list[str]  # the ingredients we hold (may be partial, see ingredient_status)
    # verified = full list from the official page; partial = key ingredients
    # only; unverified = nothing known; sample = generic sample product.
    ingredient_status: str
    warnings: list[str]
    is_sample_data: bool
    source_url: str | None
    score: int
    match_reasons: list[str]


class RoutineSuggestion(BaseModel):
    morning: list[RecommendedProduct]
    evening: list[RecommendedProduct]


class RecommendationResponse(BaseModel):
    skin_type: str
    concerns: list[str]
    matches: list[RecommendedProduct]
    routine: RoutineSuggestion
    notes: list[str]
    disclaimer: str


# ---------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------
class RoutineCompletionStat(BaseModel):
    routine_id: int
    routine_type: RoutineType
    days_logged: int
    days_completed: int
    completion_rate: float  # days_completed / days_logged, 0.0 if no logs


class ReportSummary(BaseModel):
    period_days: int
    journal_entry_count: int
    feeling_tag_counts: dict[str, int]
    routine_completion: list[RoutineCompletionStat]
    disclaimer: str
