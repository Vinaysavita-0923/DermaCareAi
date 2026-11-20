"""
Loader and lookup engine for dermacare_skin_assessment_dataset_binary.csv.

Inspected before writing any of this (see the project's handover notes),
not assumed:
  * 1120 rows, 0 nulls, 0 exact duplicates.
  * Exactly 80 (Age_Group, Skin_Type, Skin_Subtype, Sensitivity)
    combinations (5 age groups x 4 skin types x 2 subtypes each x 2
    sensitivity states), each with exactly 14 rows - one per Concern,
    except Acne (4 Internal_Type variants: Comedonal/Inflammatory/
    Fungal/Cystic) and Dark Circles (2: Pigmented/Vascular). The table
    is a complete, deterministic lookup - no fuzzy matching needed.
  * Sensitivity is literally "Yes"/"No" text, NOT the 0/1 the project
    brief assumed. There is no third state in the data, so "not sure"
    is handled here by returning both Yes and No guidance, clearly
    labelled, rather than inventing a single answer.
  * Skin_Subtype values are real strings like "T-Zone Oily Cheeks Dry"
    and "Extreme Dry" - not the brief's suggested labels (e.g. there is
    no "Balanced Combination" row at all). The subtype dropdown must be
    built from SUBTYPES_BY_DATASET_TYPE below, not invented.
  * Concern has exactly 10 real values, several of which (Dark Circles,
    Open Pores, Sun Tan) aren't in the brief's suggested concern
    checklist, and several of the brief's suggestions (Pimples, Fine
    Lines, Large Pores, Skin Texture, Excess Oiliness, Uneven Skin
    Tone) aren't backed by any row here. CONCERN_OPTIONS below is the
    real list; anything else has no ingredient-formulation data.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

_CSV_PATH = Path(__file__).parent / "dermacare_skin_assessment_dataset_binary.csv"

AGE_GROUPS: list[str] = ["14-18", "19-24", "25-36", "37-45", "45+"]
_AGE_GROUP_MAX = {"14-18": 18, "19-24": 24, "25-36": 36, "37-45": 45}  # "45+" has no max

# Our app's SkinType enum values -> the dataset's Skin_Type strings.
# "balanced" and "unsure" both land on "Normal": the dataset has no
# concept of either, and this mirrors the existing convention in
# recommendation_service.py (unsure -> balanced) rather than inventing
# a new one.
SKIN_TYPE_TO_DATASET = {
    "dry": "Dry",
    "oily": "Oily",
    "combination": "Combination",
    "balanced": "Normal",
    "unsure": "Normal",
}

# Dataset Concern label -> a stable snake_case tag, extending (not
# replacing) the existing ALLOWED_CONCERNS vocabulary in
# app/schemas/profile_schema.py.
CONCERN_LABEL_TO_TAG = {
    "Acne": "acne",
    "Dark Circles": "dark_circles",
    "Dark Spots": "dark_spots",
    "Dullness": "dullness",
    "Hyperpigmentation": "hyperpigmentation",
    "Open Pores": "open_pores",
    "Redness": "redness",
    "Sun Tan": "sun_tan",
    "Whiteheads / Blackheads": "whiteheads_blackheads",
    "Wrinkles": "wrinkles",
}
CONCERN_TAG_TO_LABEL = {v: k for k, v in CONCERN_LABEL_TO_TAG.items()}
CONCERN_OPTIONS: list[str] = list(CONCERN_LABEL_TO_TAG)  # the 10 real dataset labels


@dataclass(frozen=True)
class TreatmentRow:
    concern: str
    internal_type: str
    ingredients: str
    concentrations: str
    effects: list[str]
    treatment_profile: str


def _load() -> tuple[dict, dict]:
    """Returns (index, subtypes_by_type). index maps
    (age_group, dataset_skin_type, skin_subtype, "Yes"|"No") ->
    {concern_label: [TreatmentRow, ...]}."""
    index: dict[tuple[str, str, str, str], dict[str, list[TreatmentRow]]] = {}
    subtypes_by_type: dict[str, set[str]] = {}

    with open(_CSV_PATH, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            key = (row["Age_Group"], row["Skin_Type"], row["Skin_Subtype"], row["Sensitivity"])
            by_concern = index.setdefault(key, {})
            by_concern.setdefault(row["Concern"], []).append(
                TreatmentRow(
                    concern=row["Concern"],
                    internal_type=row["Internal_Type"],
                    ingredients=row["Ingredients"],
                    concentrations=row["Concentrations"],
                    effects=[e.strip() for e in row["Effects"].split(",") if e.strip()],
                    treatment_profile=row["Treatment_Profile"],
                )
            )
            subtypes_by_type.setdefault(row["Skin_Type"], set()).add(row["Skin_Subtype"])

    return index, {k: sorted(v) for k, v in subtypes_by_type.items()}


_INDEX, SUBTYPES_BY_DATASET_TYPE = _load()


def subtypes_for_skin_type(skin_type: str) -> list[str]:
    """skin_type is our app's SkinType enum value (e.g. "dry"). Returns
    the real dataset subtype strings for it, or [] for "unsure" (the
    spec: don't force a subtype when the user doesn't know their type)."""
    if skin_type == "unsure":
        return []
    dataset_type = SKIN_TYPE_TO_DATASET.get(skin_type)
    return SUBTYPES_BY_DATASET_TYPE.get(dataset_type, [])


def age_to_age_group(age: int) -> tuple[str, str | None]:
    """Buckets a numeric age into one of the dataset's 5 age groups.
    Returns (age_group, note) - note is set when the age falls outside
    the dataset's actual range (14-45+) and had to be clamped, since
    the dataset itself defines no bucket for e.g. a 10-year-old."""
    if age < 14:
        return "14-18", "Our dataset's youngest bracket is 14-18; results are shown for that group."
    for group, upper in _AGE_GROUP_MAX.items():
        if age <= upper:
            return group, None
    return "45+", None


def lookup(
    age_group: str,
    skin_type: str,
    skin_subtype: str | None,
    is_sensitive: bool | None,
) -> dict:
    """Looks up ingredient-formulation guidance for every concern the
    dataset covers, for this profile. Returns:
      {
        "dataset_skin_type": "Normal",
        "subtypes_used": ["Normal to Dry", "Normal to Oily"],  # 1 if known, 2 if not
        "sensitivity_states_used": ["Yes"] | ["No"] | ["Yes", "No"],
        "guidance": {concern_label: {sensitivity_state: {subtype: [TreatmentRow,...]}}},
      }
    subtypes_used has 2 entries only when skin_subtype was not given -
    we show both rather than guessing which one applies (section 4:
    don't invent results the data can't support). Same reasoning for
    sensitivity_states_used when is_sensitive is None."""
    dataset_type = SKIN_TYPE_TO_DATASET.get(skin_type, "Normal")
    subtypes = [skin_subtype] if skin_subtype else SUBTYPES_BY_DATASET_TYPE.get(dataset_type, [])
    sensitivities = ["Yes", "No"] if is_sensitive is None else (["Yes"] if is_sensitive else ["No"])

    guidance: dict[str, dict[str, dict[str, list[TreatmentRow]]]] = {
        label: {} for label in CONCERN_OPTIONS
    }
    for sensitivity in sensitivities:
        for subtype in subtypes:
            by_concern = _INDEX.get((age_group, dataset_type, subtype, sensitivity), {})
            for concern, rows in by_concern.items():
                guidance[concern].setdefault(sensitivity, {})[subtype] = rows

    return {
        "dataset_skin_type": dataset_type,
        "subtypes_used": subtypes,
        "sensitivity_states_used": sensitivities,
        "guidance": guidance,
    }
