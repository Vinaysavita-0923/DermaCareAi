"""
The "Personalized Assessment Engine": turns a saved SkinProfile into
plain-language guidance using the dataset in
app/knowledge_base/skin_assessment_dataset.py.

This does NOT duplicate product matching - app/services/
recommendation_service.py (brand + generic catalog, pregnancy/
sensitivity screening) is untouched and still the single source for
product recommendations. This module only adds the ingredient-
education layer the assessment dataset is actually good for.
"""
from __future__ import annotations

from app.database.models import SkinProfile
from app.knowledge_base.skin_assessment_dataset import (
    CONCERN_LABEL_TO_TAG,
    CONCERN_OPTIONS,
    CONCERN_TAG_TO_LABEL,
    lookup,
)
from app.schemas.profile_schema import ConcernGuidance, IngredientGuidance, PersonalizedProfileOut

DISCLAIMER = (
    "This is general ingredient education generated from a fixed reference dataset, matched to "
    "your self-reported age group, skin type/subtype and sensitivity. It is not a diagnosis, not "
    "medical advice, and not a guarantee any ingredient will work for you - patch test new "
    "actives and ask a dermatologist before starting anything for a persistent skin concern."
)


def _sensitivity_label(value: bool | None) -> str:
    return "sensitive" if value else "not sensitive"


def build_personalized_profile(profile: SkinProfile) -> PersonalizedProfileOut:
    notes: list[str] = []

    if profile.age is None or profile.age_group is None:
        notes.append(
            "No age was saved with this profile, so ingredient guidance isn't available - age "
            "group is one of the dataset's required lookup fields."
        )
        return PersonalizedProfileOut(
            skin_profile_summary=_summary(profile),
            dataset_skin_type="",
            subtypes_considered=[],
            sensitivity_considered=[],
            notes=notes,
            concerns_with_guidance=[],
            concerns_without_guidance=list(CONCERN_OPTIONS),
            disclaimer=DISCLAIMER,
        )

    result = lookup(profile.age_group, profile.skin_type.value, profile.skin_subtype, profile.is_sensitive)

    if len(result["subtypes_used"]) > 1:
        notes.append(
            "No skin subtype was saved, so guidance below covers both subtypes for your skin "
            "type - check which description matches you best."
        )
    if len(result["sensitivity_states_used"]) > 1:
        notes.append(
            "Sensitivity wasn't set to Yes or No, so guidance below is shown for both, clearly "
            "labelled - the dataset has no 'not sure' row to look up instead."
        )

    # Which of the user's own selected concerns does the dataset actually cover?
    selected_tags = set(profile.concerns or [])
    selected_labels = [CONCERN_TAG_TO_LABEL[t] for t in selected_tags if t in CONCERN_TAG_TO_LABEL]
    # Only fall back to showing all 10 when the user selected NO concerns
    # at all. If they selected concerns but none are dataset-backed
    # (e.g. only "oiliness"), respect that choice and report the gap -
    # substituting a different set of concerns they never asked about
    # would be its own kind of invented result.
    labels_to_show = selected_labels if profile.concerns else CONCERN_OPTIONS

    concerns_with_guidance: list[ConcernGuidance] = []
    concerns_without_guidance: list[str] = []
    for label in labels_to_show:
        variants: dict[str, list[IngredientGuidance]] = {}
        for sensitivity, by_subtype in result["guidance"].get(label, {}).items():
            for subtype, rows in by_subtype.items():
                key = f"{sensitivity}|{subtype}"
                variants[key] = [
                    IngredientGuidance(
                        internal_type=r.internal_type,
                        ingredients=r.ingredients,
                        concentrations=r.concentrations,
                        effects=r.effects,
                        treatment_profile=r.treatment_profile,
                    )
                    for r in rows
                ]
        if variants:
            concerns_with_guidance.append(ConcernGuidance(concern=label, variants=variants))
        else:
            concerns_without_guidance.append(label)

    other_selected = selected_tags - set(CONCERN_LABEL_TO_TAG.values())
    if other_selected:
        notes.append(
            "No ingredient-formulation data exists in our current dataset for: "
            + ", ".join(sorted(other_selected))
            + ". These remain saved on your profile and are still used for product filtering."
        )

    return PersonalizedProfileOut(
        skin_profile_summary=_summary(profile),
        dataset_skin_type=result["dataset_skin_type"],
        subtypes_considered=result["subtypes_used"],
        sensitivity_considered=[_sensitivity_label(s == "Yes") for s in result["sensitivity_states_used"]],
        notes=notes,
        concerns_with_guidance=concerns_with_guidance,
        concerns_without_guidance=concerns_without_guidance,
        disclaimer=DISCLAIMER,
    )


def _summary(profile: SkinProfile) -> str:
    parts = [f"{profile.skin_type.value} skin"]
    if profile.skin_subtype:
        parts.append(f" ({profile.skin_subtype})")
    if profile.age_group:
        parts.append(f", age group {profile.age_group}")
    if profile.is_sensitive is True:
        parts.append(", sensitive")
    elif profile.is_sensitive is False:
        parts.append(", not sensitive")
    else:
        parts.append(", sensitivity not sure")
    if profile.concerns:
        parts.append(". Main concerns: " + ", ".join(profile.concerns))
    return "".join(parts).strip()
