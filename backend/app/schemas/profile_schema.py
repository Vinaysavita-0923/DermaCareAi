"""
Request/response shapes for the skin-profile endpoints.

Important framing (from the project brief): a skin profile is
user-selected *preference* data used to personalize educational
content — NOT a diagnosis and NOT a clinical record. The field names
and the API docstrings keep that framing so nothing here reads as a
medical assessment.
"""
from __future__ import annotations

import datetime

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from app.database.models import SkinType
from app.knowledge_base.skin_assessment_dataset import CONCERN_TAG_TO_LABEL, subtypes_for_skin_type

# A small, closed vocabulary for concern tags, so free-text medical
# terms don't creep in. These are everyday descriptive words, not
# diagnoses. The second line extends the original 7 with tags derived
# from the real assessment dataset's Concern column (see
# app/knowledge_base/skin_assessment_dataset.py) - added, not replaced,
# so existing saved profiles and the chat agent's tag matching keep
# working unchanged.
ALLOWED_CONCERNS = {"acne", "dryness", "redness", "texture", "oiliness", "sensitivity", "dullness"}
ALLOWED_CONCERNS |= set(CONCERN_TAG_TO_LABEL)


class SkinProfileUpdate(BaseModel):
    """Everything is optional — a user can set just their skin type, or
    just their concerns, without having to resend the whole profile.
    Omitted fields are left unchanged; see the PUT endpoint.

    `is_sensitive` is a tri-state the dataset itself doesn't have a
    third value for: True ("Yes"), False ("No"), or omitted/None
    ("Not sure" — the lookup engine then shows both Yes and No
    guidance rather than guessing)."""

    # Not a SkinProfile column — the assessment form collects it, but it
    # is written to the existing User.full_name instead of being stored
    # a second time (the project brief: "Do not duplicate user
    # records"). Popped out of `changes` before any SkinProfile write.
    full_name: str | None = None
    age: int | None = None
    skin_type: SkinType | None = None
    skin_subtype: str | None = None
    is_sensitive: bool | None = None
    concerns: list[str] | None = None
    sensitivity_notes: str | None = None
    avoid_ingredients: list[str] | None = None

    @field_validator("full_name")
    @classmethod
    def _clean_full_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            return None
        if len(value) > 255:
            raise ValueError("Full name must be 255 characters or fewer.")
        return value

    @field_validator("age")
    @classmethod
    def _validate_age(cls, value: int | None) -> int | None:
        if value is None:
            return None
        if not (1 <= value <= 120):
            raise ValueError("Age must be between 1 and 120.")
        return value

    @model_validator(mode="after")
    def _validate_subtype_matches_type(self) -> "SkinProfileUpdate":
        # Only checked when both are present in THIS request — a PUT
        # that sends just {"skin_subtype": "..."} can't be validated
        # against a skin_type that lives on the already-saved row, so
        # that cross-check happens in the API layer instead, where the
        # saved profile is available.
        if self.skin_type is not None and self.skin_subtype is not None:
            valid = subtypes_for_skin_type(self.skin_type.value)
            if self.skin_type.value == "unsure":
                raise ValueError("A skin subtype can't be set while skin type is 'unsure'.")
            if self.skin_subtype not in valid:
                raise ValueError(
                    f"'{self.skin_subtype}' is not a valid subtype for {self.skin_type.value}. "
                    f"Valid options: {valid}"
                )
        return self

    @field_validator("concerns")
    @classmethod
    def _validate_concerns(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        cleaned = [c.strip().lower() for c in value if c.strip()]
        invalid = [c for c in cleaned if c not in ALLOWED_CONCERNS]
        if invalid:
            raise ValueError(
                f"Unknown concern(s): {invalid}. Allowed values: "
                f"{sorted(ALLOWED_CONCERNS)}"
            )
        # De-duplicate while preserving order.
        return list(dict.fromkeys(cleaned))

    @field_validator("avoid_ingredients")
    @classmethod
    def _clean_ingredients(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        cleaned = [i.strip() for i in value if i.strip()]
        return list(dict.fromkeys(cleaned))

    @field_validator("sensitivity_notes")
    @classmethod
    def _limit_notes_length(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if len(value) > 1000:
            raise ValueError("Sensitivity notes must be 1000 characters or fewer.")
        return value or None


class SkinProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    skin_type: SkinType
    skin_subtype: str | None
    age: int | None
    age_group: str | None
    is_sensitive: bool | None
    concerns: list[str] | None
    sensitivity_notes: str | None
    avoid_ingredients: list[str] | None
    created_at: datetime.datetime
    updated_at: datetime.datetime


class AssessmentHistoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    age: int | None
    age_group: str | None
    skin_type: SkinType
    skin_subtype: str | None
    is_sensitive: bool | None
    concerns: list[str] | None
    sensitivity_notes: str | None
    created_at: datetime.datetime


class IngredientGuidance(BaseModel):
    """One dataset row's formulation guidance for a single concern."""

    internal_type: str
    ingredients: str
    concentrations: str
    effects: list[str]
    treatment_profile: str


class ConcernGuidance(BaseModel):
    """All guidance found for one concern. `variants` is keyed
    "<sensitivity>|<subtype>" so the caller can see exactly which
    assumptions each set of rows is under when the profile didn't
    specify a subtype and/or sensitivity (see skin_assessment_dataset.
    lookup's docstring) — never silently picking one for the user."""

    concern: str
    variants: dict[str, list[IngredientGuidance]]


class PersonalizedProfileOut(BaseModel):
    """The Phase-4 'Personalized Assessment Engine' output: a plain-
    language summary plus per-concern ingredient education, grounded
    only in what the dataset actually contains."""

    skin_profile_summary: str
    dataset_skin_type: str
    subtypes_considered: list[str]
    sensitivity_considered: list[str]
    notes: list[str]
    concerns_with_guidance: list[ConcernGuidance]
    concerns_without_guidance: list[str]
    disclaimer: str
