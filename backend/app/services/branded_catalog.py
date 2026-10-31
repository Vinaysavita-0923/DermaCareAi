"""
App layer on top of the DermaCare branded catalog
(app/knowledge_base/dermacare_catalog_improved.py + dermacare_products_improved.json).

The dataset is a research starter list: only 112 of 250 records are
eligible (official listing seen), and only a handful have a full
ingredient list. So this layer adds the safety behaviour the raw scorer
does not have:

  * Unverified candidates are never used (kept out of the DB and recs).
  * Near-duplicate size variants (e.g. "125 ml" / "1000 ml") collapse to one.
  * Every product gets an ingredient_status - verified (full INCI from the
    official page), partial (key ingredients only) or unverified (nothing).
  * Pregnancy caution, sensitive skin and avoided ingredients are checked
    against the product NAME as well as its ingredient data.
  * When any of those safety settings is on, only products with a FULL
    ingredient list are screened and shown (the improved catalog's rule:
    highlights are not a complete list, so absence cannot be inferred).
    Otherwise partial / unverified products are shown with a "check the
    pack" warning.
  * Retinoids and exfoliants are never auto-placed in a suggested routine,
    and day/night products are kept in the right slot.

No prices, availability or medical claims are produced here.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from functools import lru_cache

from app.knowledge_base import dermacare_catalog_improved as dc

# Categories the app is willing to recommend (bundles, body care and
# make-up removers are in the dataset but not skin-care routine steps).
RECOMMENDABLE_CATEGORIES = {
    "cleanser", "toner", "serum", "moisturizer", "sunscreen", "exfoliant",
    "spot_treatment", "mask", "treatment", "essence", "face_oil", "eye_cream",
}
BASIC_CATEGORIES = {"cleanser", "moisturizer", "sunscreen"}
# At most one of these per list, so recommendations don't pile up actives.
ACTIVE_CATEGORIES = {"exfoliant", "spot_treatment", "treatment"}

RETINOIDS = ("retinol", "retinal", "retinoid", "retinyl")
_ACIDS = ("salicylic", "glycolic", "lactic", "mandelic", "benzoyl", "azelaic")
_ACID_WORDS = re.compile(r"\b(aha|bha|lha)\b")

# Conservative app rules - NOT clinical advice (the UI and disclaimer say so).
PREGNANCY_TERMS = RETINOIDS + _ACIDS + ("vitamin c", "ascorbic")
SENSITIVE_TERMS = RETINOIDS + _ACIDS + (
    "vitamin c", "ascorbic", "fragrance", "parfum", "tea tree", "alcohol denat", "kojic",
)

_SIZE_RE = re.compile(r"\b\d+(?:\.\d+)?\s?(?:ml|g|gm|oz)\b", re.I)
_NIGHT_RE = re.compile(r"\b(night|pm|overnight|sleeping)\b", re.I)
_DAY_RE = re.compile(r"\b(am|day)\b|spf|sunscreen|sun lotion", re.I)

STATUS_RANK = {"verified": 0, "partial": 1, "unverified": 2}


# ---------------------------------------------------------------------
# Loading / de-duplicating
# ---------------------------------------------------------------------
@lru_cache(maxsize=1)
def _guidance() -> dict[str, str]:
    payload = json.loads(dc.DATA_PATH.read_text(encoding="utf-8"))
    return payload.get("general_usage_guidance_not_product_specific", {})


def norm_name(name: str) -> str:
    return re.sub(r"\s+", " ", _SIZE_RE.sub("", name)).strip().casefold()


def ingredient_status(p: dict) -> str:
    if p.get("full_ingredients_inci"):
        return "verified"
    if p.get("ingredient_highlights"):
        return "partial"
    return "unverified"


def _quality(p: dict) -> tuple:
    # Higher is better when choosing between duplicates of one product.
    return (1 if p.get("full_ingredients_inci") else 0, len(p.get("ingredient_highlights") or []))


@lru_cache(maxsize=1)
def unique_eligible_products() -> tuple[dict, ...]:
    """Eligible records, with size variants collapsed to the best record."""
    best: dict[tuple[str, str], dict] = {}
    for p in dc.load_catalog():
        if p["verification_status"] not in dc.ELIGIBLE_STATUSES:
            continue
        if p["category"] not in RECOMMENDABLE_CATEGORIES:
            continue
        key = (p["brand"].casefold(), norm_name(p["product_name"]))
        if key not in best or _quality(p) > _quality(best[key]):
            best[key] = p
    return tuple(sorted(best.values(), key=lambda x: x["id"]))


def product_text(p: dict) -> str:
    parts = [p["product_name"], *(p.get("ingredient_highlights") or []), *(p.get("full_ingredients_inci") or [])]
    return " ".join(parts).lower()


def has_retinoid(p: dict) -> bool:
    t = product_text(p)
    return any(k in t for k in RETINOIDS)


def _has_any(text: str, terms: tuple[str, ...]) -> bool:
    return any(t in text for t in terms) or bool(_ACID_WORDS.search(text))


# ---------------------------------------------------------------------
# Display helpers (used by the DB seed and the recommendations)
# ---------------------------------------------------------------------
def how_to_use(p: dict) -> str:
    key = "retinoid" if has_retinoid(p) else p["category"]
    return _guidance().get(key, "Use as directed on the product label.")


def status_label(p: dict) -> str:
    if p["verification_status"] == "official_product_page_ingredient_list_seen":
        return "Ingredient list copied from the official product page."
    return "Listed in the brand's official catalog; ingredients not independently verified."


def source_text(p: dict) -> str:
    return f"{p['source_url']} (checked {p['last_checked']}). {status_label(p)}"[:500]


def description_for(p: dict) -> str:
    cat = p["category"].replace("_", " ")
    skin = p.get("skin_types") or []
    skin_txt = "all skin types" if "all" in skin else (", ".join(skin) + " skin" if skin else "")
    lines = [f"{p['brand']} {cat}" + (f", tagged for {skin_txt}." if skin_txt else ".")]
    if p.get("concerns"):
        lines.append("Commonly chosen for: " + ", ".join(c.replace("_", " ") for c in p["concerns"]) + ".")
    if p.get("ingredient_highlights"):
        lines.append("Key ingredients (not a full list): " + ", ".join(p["ingredient_highlights"]) + ".")
    lines.append(status_label(p))
    lines.append("How to use: " + how_to_use(p))
    lines.append("Always check the current pack for the full ingredient list and directions.")
    return "\n".join(lines)


# ---------------------------------------------------------------------
# Matching
# ---------------------------------------------------------------------
@dataclass
class Match:
    product: dict
    score: int
    reasons: list[str]
    warnings: list[str] = field(default_factory=list)
    status: str = "unverified"


def recommend(
    *,
    skin_type: str,
    concerns: list[str],
    avoid: list[str],
    pregnant_or_trying: bool,
) -> list[Match]:
    """All suitable branded products, best first (deduplicated, eligible only)."""
    concerns_set = set(concerns)
    sensitive = "sensitivity" in concerns_set
    avoid_terms = [a.strip().casefold() for a in avoid if a.strip()]
    strict = bool(avoid_terms) or sensitive or pregnant_or_trying

    out: list[Match] = []
    for p in unique_eligible_products():
        status = ingredient_status(p)
        text = product_text(p)

        # Skin type must fit (the raw scorer only penalises a mismatch).
        sts = {x.casefold() for x in p.get("skin_types") or []}
        if not ("all" in sts or skin_type in sts or (sensitive and "sensitive" in sts)):
            continue

        # Safety exclusions, checked on name + highlights + INCI.
        if any(a in text for a in avoid_terms):
            continue
        if pregnant_or_trying and _has_any(text, PREGNANCY_TERMS):
            continue
        if sensitive and _has_any(text, SENSITIVE_TERMS):
            continue
        # Safety screening needs a full ingredient list. Highlights are not a
        # complete list, so absence of an ingredient cannot be inferred - the
        # catalog's own rule. Without one, the product is withheld, not "safe".
        if strict and status != "verified":
            continue

        base = dc.score_product(
            p,
            skin_type=skin_type,
            concerns=list(concerns_set),
            sensitive=sensitive,
            excluded_ingredients=avoid,
            pregnant_or_trying=pregnant_or_trying,
        )
        if base is None:
            continue

        reasons = list(base["match_reasons"])
        warnings: list[str] = []
        if status == "unverified":
            warnings.append("Ingredient list not verified - check the pack.")
        elif status == "partial":
            warnings.append("Only key ingredients are listed here, not the full list - check the pack.")
        if status != "verified":
            if avoid_terms:
                warnings.append("Check the pack for ingredients you avoid: " + ", ".join(avoid) + ".")
            if sensitive:
                warnings.append("Fragrance and other irritants are not confirmed - patch test first.")
            if pregnant_or_trying:
                warnings.append("Check the label with a doctor or pharmacist while pregnant or trying to conceive.")
        if has_retinoid(p):
            warnings.append("Contains a vitamin A (retinoid) - can irritate; not for use in pregnancy.")

        out.append(Match(p, base["score"], reasons, warnings, status))

    out.sort(key=lambda m: (-m.score, STATUS_RANK[m.status], m.product["brand"], m.product["product_name"]))
    return out


def display_matches(matches: list[Match], per_category: int = 2) -> list[Match]:
    """Trim to a varied list: at most `per_category` per category, one active."""
    counts: dict[str, int] = {}
    kept: list[Match] = []
    for m in matches:
        cat = m.product["category"]
        # Beyond the basic routine steps, only show products that speak to a
        # concern the user picked, not ones that merely fit their skin type.
        if cat not in BASIC_CATEGORIES and not any(r.startswith("concern tag match") for r in m.reasons):
            continue
        limit = 1 if cat in ACTIVE_CATEGORIES else per_category
        if counts.get(cat, 0) >= limit:
            continue
        counts[cat] = counts.get(cat, 0) + 1
        kept.append(m)
    return kept


def time_ok(name: str, slot: str) -> bool:
    """Keep night products out of the morning and sun/day products out of the evening."""
    if slot == "morning":
        return not _NIGHT_RE.search(name)
    return not _DAY_RE.search(name)


def routine_pick(matches: list[Match], category: str, slot: str) -> Match | None:
    for m in matches:
        p = m.product
        if p["category"] != category or not time_ok(p["product_name"], slot):
            continue
        if has_retinoid(p):  # never auto-place a retinoid in a routine
            continue
        return m
    return None
