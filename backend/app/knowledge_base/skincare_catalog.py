"""
Educational sample catalog: ingredients + generic product archetypes.

IMPORTANT (per the project brief: "do not invent availability, prices,
or medical effectiveness"):
  * Products here are GENERIC ARCHETYPES (e.g. "Salicylic Acid Foaming
    Cleanser"), not real branded listings. Brand is "Sample (generic)".
  * Wording is "commonly used for" / "may help", never "treats" or "cures".
  * Every row is saved with is_sample_data=True and a `source` note.
  * No prices and no availability anywhere.

Vocabulary:
  skin_types : dry, oily, combination, balanced   (matches SkinType enum)
  concerns   : acne, dryness, redness, texture, oiliness, sensitivity, dullness
               (matches ALLOWED_CONCERNS in profile_schema.py)
"""
from __future__ import annotations

SOURCE = (
    "Educational sample data based on general, widely published skin-care "
    "information. Generic product type, not a real product listing."
)

ALL = ["dry", "oily", "combination", "balanced"]
OILY = ["oily", "combination"]
DRY = ["dry", "balanced"]

# ---------------------------------------------------------------------
# INGREDIENTS
# ---------------------------------------------------------------------
INGREDIENTS = [
    {"name": "Niacinamide", "category": "Vitamin B3",
     "description": "A form of vitamin B3 found in many serums and moisturizers.",
     "uses": "Commonly used to help with the look of enlarged pores, uneven texture and excess oil, and to support the skin barrier.",
     "skin_types": ALL, "concerns": ["oiliness", "texture", "acne", "dullness"],
     "precautions": "Usually well tolerated. Start with a lower strength and use every other day at first.", "irritant": False},
    {"name": "Hyaluronic Acid", "category": "Humectant",
     "description": "A moisture-binding ingredient that holds water in the upper layer of skin.",
     "uses": "Commonly used to add lightweight hydration and a plumper look to the skin.",
     "skin_types": ALL, "concerns": ["dryness", "dullness"],
     "precautions": "Apply on slightly damp skin and seal with a moisturizer so it does not feel tight.", "irritant": False},
    {"name": "Glycerin", "category": "Humectant",
     "description": "A very common, gentle moisturizing ingredient.",
     "uses": "Commonly used to draw moisture into the skin and reduce a dry, tight feeling.",
     "skin_types": ALL, "concerns": ["dryness"],
     "precautions": "Generally well tolerated.", "irritant": False},
    {"name": "Ceramides", "category": "Barrier lipid",
     "description": "Fats that naturally occur in the skin and help form its protective barrier.",
     "uses": "Commonly used in moisturizers to support the skin barrier and reduce dryness and tightness.",
     "skin_types": ["dry", "balanced", "combination"], "concerns": ["dryness", "sensitivity", "redness"],
     "precautions": "Generally well tolerated.", "irritant": False},
    {"name": "Squalane", "category": "Emollient",
     "description": "A light, non-greasy oil-like moisturizer.",
     "uses": "Commonly used to soften skin and lock in moisture without a heavy feel.",
     "skin_types": ALL, "concerns": ["dryness", "dullness"],
     "precautions": "Generally well tolerated.", "irritant": False},
    {"name": "Panthenol (Vitamin B5)", "category": "Soothing / humectant",
     "description": "A provitamin of B5 used for hydration and comfort.",
     "uses": "Commonly used in products meant to soothe and hydrate dry or easily irritated skin.",
     "skin_types": ALL, "concerns": ["dryness", "sensitivity", "redness"],
     "precautions": "Generally well tolerated.", "irritant": False},
    {"name": "Centella Asiatica", "category": "Plant extract",
     "description": "A plant extract (also called cica or gotu kola) used in calming skin-care.",
     "uses": "Commonly used in soothing products for skin that looks red or feels sensitive.",
     "skin_types": ALL, "concerns": ["redness", "sensitivity", "acne"],
     "precautions": "Patch test if you have plant allergies.", "irritant": False},
    {"name": "Aloe Vera", "category": "Plant extract",
     "description": "A water-rich plant gel used in light, cooling products.",
     "uses": "Commonly used to hydrate and cool the skin.",
     "skin_types": ALL, "concerns": ["redness", "dryness", "sensitivity"],
     "precautions": "Patch test first; some people react to aloe-based products.", "irritant": False},
    {"name": "Allantoin", "category": "Soothing agent",
     "description": "A mild skin-conditioning ingredient.",
     "uses": "Commonly used to soften and calm skin in gentle formulas.",
     "skin_types": ALL, "concerns": ["sensitivity", "dryness"],
     "precautions": "Generally well tolerated.", "irritant": False},
    {"name": "Shea Butter", "category": "Emollient",
     "description": "A rich plant butter used in heavier moisturizers.",
     "uses": "Commonly used to soften and seal in moisture on dry skin.",
     "skin_types": ["dry"], "concerns": ["dryness"],
     "precautions": "Can feel heavy on oily or acne-prone skin.", "irritant": False},
    {"name": "Petrolatum", "category": "Occlusive",
     "description": "A thick occlusive that forms a barrier to reduce water loss.",
     "uses": "Commonly used on very dry patches to seal in moisture.",
     "skin_types": ["dry"], "concerns": ["dryness"],
     "precautions": "Heavy feel; usually not preferred on oily skin.", "irritant": False},
    {"name": "Dimethicone", "category": "Silicone",
     "description": "A silicone that gives products a smooth, silky slip.",
     "uses": "Commonly used to smooth skin feel and reduce moisture loss.",
     "skin_types": ALL, "concerns": ["dryness", "texture"],
     "precautions": "Generally well tolerated.", "irritant": False},
    {"name": "Salicylic Acid", "category": "BHA exfoliant",
     "description": "A beta-hydroxy acid that is oil-soluble, so it can work inside pores.",
     "uses": "Commonly used to help with blackheads, clogged pores and breakouts on oily or combination skin.",
     "skin_types": OILY, "concerns": ["acne", "oiliness", "texture"],
     "precautions": "Can cause dryness or stinging. Start 2-3 times a week and always use sunscreen. Ask a doctor first if pregnant.", "irritant": True},
    {"name": "Glycolic Acid", "category": "AHA exfoliant",
     "description": "A small, water-soluble alpha-hydroxy acid that exfoliates the skin surface.",
     "uses": "Commonly used to smooth rough texture and brighten a dull look.",
     "skin_types": ["balanced", "combination", "oily"], "concerns": ["texture", "dullness"],
     "precautions": "Can irritate and increases sun sensitivity. Use at night, 1-2 times a week to start, with daily sunscreen.", "irritant": True},
    {"name": "Lactic Acid", "category": "AHA exfoliant",
     "description": "A milder alpha-hydroxy acid that also helps attract moisture.",
     "uses": "Commonly used for gentle exfoliation on dry or normal skin to smooth texture.",
     "skin_types": ["dry", "balanced", "combination"], "concerns": ["texture", "dullness", "dryness"],
     "precautions": "May tingle. Use sunscreen daily and start with once a week.", "irritant": True},
    {"name": "Azelaic Acid", "category": "Multi-purpose acid",
     "description": "An acid found in grains, used in creams and gels.",
     "uses": "Commonly used for breakouts and for redness or uneven-looking tone.",
     "skin_types": ALL, "concerns": ["acne", "redness", "texture"],
     "precautions": "May cause mild tingling at first. Patch test and build up slowly.", "irritant": False},
    {"name": "Benzoyl Peroxide", "category": "Acne active",
     "description": "An over-the-counter ingredient used on breakout-prone skin.",
     "uses": "Commonly used on active pimples to reduce acne-causing bacteria.",
     "skin_types": OILY, "concerns": ["acne"],
     "precautions": "Can dry, peel and bleach fabrics. Use a low strength (2.5%) on spots only, start slowly.", "irritant": True},
    {"name": "Retinol", "category": "Vitamin A",
     "description": "A vitamin A derivative used in night-time products.",
     "uses": "Commonly used to help with fine lines, uneven texture and a dull look over several weeks.",
     "skin_types": ["balanced", "oily", "combination"], "concerns": ["texture", "dullness"],
     "precautions": "Can cause dryness and peeling. Start twice a week at night with sunscreen in the morning. Not recommended during pregnancy; check with a doctor.", "irritant": True},
    {"name": "Vitamin C (Ascorbic Acid)", "category": "Antioxidant",
     "description": "An antioxidant used in morning serums.",
     "uses": "Commonly used to help brighten a dull look and support the skin against daily environmental stress.",
     "skin_types": ["balanced", "oily", "combination", "dry"], "concerns": ["dullness", "texture"],
     "precautions": "Can sting on sensitive skin. Start with a lower strength and store away from light and air.", "irritant": True},
    {"name": "Zinc PCA", "category": "Oil-balancing mineral",
     "description": "A zinc salt used in products for oily skin.",
     "uses": "Commonly used to help control shine and the look of excess oil.",
     "skin_types": OILY, "concerns": ["oiliness", "acne"],
     "precautions": "Generally well tolerated.", "irritant": False},
    {"name": "Zinc Oxide", "category": "Mineral UV filter",
     "description": "A mineral sunscreen ingredient that sits on the skin and reflects UV.",
     "uses": "Commonly used in sunscreens, especially for sensitive skin.",
     "skin_types": ALL, "concerns": ["sensitivity", "redness"],
     "precautions": "May leave a white cast on deeper skin tones; reapply every 2 hours outdoors.", "irritant": False},
    {"name": "Titanium Dioxide", "category": "Mineral UV filter",
     "description": "A mineral sunscreen ingredient, often paired with zinc oxide.",
     "uses": "Commonly used in sunscreens for sensitive skin.",
     "skin_types": ALL, "concerns": ["sensitivity"],
     "precautions": "May leave a slight white cast.", "irritant": False},
    {"name": "Chemical UV Filters", "category": "UV filter",
     "description": "Sunscreen ingredients such as avobenzone that absorb UV light.",
     "uses": "Commonly used in lightweight, invisible-finish sunscreens.",
     "skin_types": ALL, "concerns": [],
     "precautions": "Some people with sensitive skin find these stinging, especially near eyes.", "irritant": True},
    {"name": "Kaolin Clay", "category": "Clay",
     "description": "A mild clay that absorbs oil from the skin surface.",
     "uses": "Commonly used in masks and cleansers for oily skin to reduce shine.",
     "skin_types": OILY, "concerns": ["oiliness", "acne"],
     "precautions": "Can over-dry if left on too long; do not use daily.", "irritant": False},
    {"name": "Green Tea Extract", "category": "Antioxidant",
     "description": "A plant extract rich in antioxidants.",
     "uses": "Commonly used in lightweight products to calm the look of redness and excess oil.",
     "skin_types": ALL, "concerns": ["redness", "oiliness"],
     "precautions": "Generally well tolerated.", "irritant": False},
    {"name": "Tea Tree Oil", "category": "Essential oil",
     "description": "An essential oil used in some spot treatments.",
     "uses": "Commonly used in small amounts in spot products for breakout-prone skin.",
     "skin_types": OILY, "concerns": ["acne"],
     "precautions": "Can irritate or cause allergic reactions. Never use undiluted. Avoid with sensitive skin.", "irritant": True},
    {"name": "Fragrance", "category": "Added scent",
     "description": "Added perfume (also listed as parfum).",
     "uses": "Adds scent only; has no skin benefit.",
     "skin_types": [], "concerns": [],
     "precautions": "A common cause of irritation and allergy. Avoid if your skin is sensitive.", "irritant": True},
    {"name": "Alcohol Denat.", "category": "Solvent",
     "description": "A drying alcohol used to make products feel fast-drying.",
     "uses": "Used for a quick-drying, mattifying feel.",
     "skin_types": ["oily"], "concerns": [],
     "precautions": "Can dry or sting, especially on dry or sensitive skin.", "irritant": True},
]

# ---------------------------------------------------------------------
# PRODUCTS (generic archetypes)
# ---------------------------------------------------------------------
BRAND = "Sample (generic)"

PRODUCTS = [
    # ---------------- Cleansers ----------------
    {"name": "Gentle Gel Cleanser", "category": "cleanser", "usage_time": "both",
     "skin_types": OILY + ["balanced"], "concerns": ["oiliness", "acne"],
     "description": "A light, fragrance-free gel cleanser that rinses clean without a tight feeling.",
     "uses": "Daily face wash to remove oil, sweat and dirt.",
     "how_to_use": "Massage onto damp skin for 30-60 seconds, rinse with lukewarm water. Morning and night.",
     "cautions": "Avoid contact with eyes.", "ingredients": ["Glycerin", "Panthenol (Vitamin B5)"]},
    {"name": "Hydrating Cream Cleanser", "category": "cleanser", "usage_time": "both",
     "skin_types": ["dry", "balanced"], "concerns": ["dryness", "sensitivity"],
     "description": "A creamy, non-foaming cleanser that leaves skin soft.",
     "uses": "Gentle daily cleansing for dry or tight-feeling skin.",
     "how_to_use": "Apply to dry or damp skin, massage, rinse or wipe off with a soft cloth.",
     "cautions": None, "ingredients": ["Glycerin", "Ceramides", "Allantoin"]},
    {"name": "Salicylic Acid Foaming Cleanser", "category": "cleanser", "usage_time": "both",
     "skin_types": ["oily"], "concerns": ["acne", "oiliness"],
     "description": "A foaming wash with a low level of salicylic acid for clogged pores.",
     "uses": "Daily cleansing for oily, breakout-prone skin.",
     "how_to_use": "Use once daily at first (evening), then twice daily if skin tolerates it. Leave on for 30 seconds, rinse well.",
     "cautions": "May dry the skin. Moisturize after. Use sunscreen in the morning.",
     "ingredients": ["Salicylic Acid", "Zinc PCA", "Glycerin"]},
    {"name": "Fragrance-Free Milk Cleanser", "category": "cleanser", "usage_time": "both",
     "skin_types": ["dry", "balanced", "combination"], "concerns": ["sensitivity", "redness", "dryness"],
     "description": "A very mild milky cleanser made without fragrance for easily irritated skin.",
     "uses": "Gentle cleansing for sensitive or redness-prone skin.",
     "how_to_use": "Massage onto skin with fingertips and rinse with lukewarm water.",
     "cautions": None, "ingredients": ["Glycerin", "Panthenol (Vitamin B5)", "Allantoin"]},
    {"name": "Oil-Control Clay Cleanser", "category": "cleanser", "usage_time": "morning",
     "skin_types": ["oily"], "concerns": ["oiliness", "acne"],
     "description": "A clay-based cleanser that helps reduce shine.",
     "uses": "Morning cleansing for very oily skin.",
     "how_to_use": "Use on damp skin in the morning, rinse thoroughly.",
     "cautions": "Not for daily use if skin feels tight.", "ingredients": ["Kaolin Clay", "Glycerin"]},
    {"name": "Balancing Gel Cleanser", "category": "cleanser", "usage_time": "both",
     "skin_types": ["combination", "balanced"], "concerns": ["oiliness", "dullness"],
     "description": "A soft gel cleanser for skin that is oily in some areas and normal or dry in others.",
     "uses": "Everyday cleanser that does not over-strip.",
     "how_to_use": "Massage onto damp skin and rinse. Morning and night.",
     "cautions": None, "ingredients": ["Glycerin", "Green Tea Extract"]},

    # ---------------- Toners ----------------
    {"name": "Hydrating Essence Toner", "category": "toner", "usage_time": "both",
     "skin_types": ["dry", "balanced", "combination"], "concerns": ["dryness", "dullness"],
     "description": "A watery, alcohol-free toner that adds a first layer of hydration.",
     "uses": "Boosts hydration after cleansing and prepares skin for serum and moisturizer.",
     "how_to_use": "Pat a few drops into clean skin with your hands. Morning and night.",
     "cautions": None, "ingredients": ["Hyaluronic Acid", "Glycerin", "Panthenol (Vitamin B5)"]},
    {"name": "Mild BHA Toner", "category": "toner", "usage_time": "night",
     "skin_types": ["oily"], "concerns": ["acne", "oiliness", "texture"],
     "description": "A low-strength salicylic acid toner for blackheads and clogged pores.",
     "uses": "Mild exfoliation for oily, congested skin.",
     "how_to_use": "Apply with a cotton pad at night, 2-3 times a week at first.",
     "cautions": "Can cause dryness. Always wear sunscreen the next day. Skip if skin is irritated.",
     "ingredients": ["Salicylic Acid", "Green Tea Extract", "Panthenol (Vitamin B5)"]},
    {"name": "Soothing Centella Toner", "category": "toner", "usage_time": "both",
     "skin_types": ALL, "concerns": ["redness", "sensitivity", "acne"],
     "description": "A calming, fragrance-free toner with centella.",
     "uses": "Calms the look of redness and irritated-feeling skin.",
     "how_to_use": "Press onto clean skin after cleansing.",
     "cautions": None, "ingredients": ["Centella Asiatica", "Panthenol (Vitamin B5)", "Allantoin"]},

    # ---------------- Serums ----------------
    {"name": "Niacinamide 5% Serum", "category": "serum", "usage_time": "both",
     "skin_types": ["oily", "combination", "balanced"], "concerns": ["oiliness", "acne", "texture", "dullness"],
     "description": "A lightweight serum with a moderate level of niacinamide.",
     "uses": "Commonly used for the look of pores, shine and uneven texture.",
     "how_to_use": "Apply 2-3 drops to clean skin before moisturizer. Start every other day.",
     "cautions": "Reduce use if you notice flushing or irritation.",
     "ingredients": ["Niacinamide", "Zinc PCA", "Glycerin"]},
    {"name": "Hyaluronic Acid Hydrating Serum", "category": "serum", "usage_time": "both",
     "skin_types": ALL, "concerns": ["dryness", "dullness"],
     "description": "A water-light serum for deep-feeling hydration.",
     "uses": "Adds hydration for dry, dehydrated or dull-looking skin.",
     "how_to_use": "Apply to slightly damp skin, then follow with moisturizer.",
     "cautions": None, "ingredients": ["Hyaluronic Acid", "Glycerin", "Panthenol (Vitamin B5)"]},
    {"name": "Vitamin C Brightening Serum", "category": "serum", "usage_time": "morning",
     "skin_types": ["balanced", "combination", "oily", "dry"], "concerns": ["dullness", "texture"],
     "description": "An antioxidant serum used in the morning under sunscreen.",
     "uses": "Commonly used to brighten a dull-looking complexion.",
     "how_to_use": "Apply a few drops in the morning after cleansing, then moisturizer and sunscreen.",
     "cautions": "May sting sensitive skin. Start with every other day.",
     "ingredients": ["Vitamin C (Ascorbic Acid)", "Hyaluronic Acid"]},
    {"name": "Azelaic Acid Gel", "category": "serum", "usage_time": "both",
     "skin_types": ALL, "concerns": ["acne", "redness", "texture"],
     "description": "A gentle-leaning acid gel used for breakouts and redness.",
     "uses": "Commonly used on skin with breakouts, redness or uneven tone.",
     "how_to_use": "Apply a thin layer once daily, then up to twice daily if tolerated.",
     "cautions": "Mild tingling is possible at first.", "ingredients": ["Azelaic Acid", "Glycerin"]},
    {"name": "Beginner Retinol Serum", "category": "serum", "usage_time": "night",
     "skin_types": ["balanced", "oily", "combination"], "concerns": ["texture", "dullness"],
     "description": "A low-strength retinol serum for first-time users.",
     "uses": "Commonly used over several weeks for uneven texture and a dull look.",
     "how_to_use": "Use a pea-sized amount at night, twice a week at first, building up slowly. Moisturize after.",
     "cautions": "Not for use during pregnancy. Can cause peeling and dryness. Use sunscreen every morning. Avoid if skin is sensitive or irritated.",
     "ingredients": ["Retinol", "Squalane", "Glycerin"]},
    {"name": "Ceramide Barrier Serum", "category": "serum", "usage_time": "both",
     "skin_types": ["dry", "balanced", "combination"], "concerns": ["dryness", "sensitivity", "redness"],
     "description": "A fragrance-free serum to support a dry or easily irritated skin barrier.",
     "uses": "Helps reduce tightness and supports comfort on dry or reactive skin.",
     "how_to_use": "Apply to clean skin before moisturizer.",
     "cautions": None, "ingredients": ["Ceramides", "Panthenol (Vitamin B5)", "Hyaluronic Acid"]},
    {"name": "Calming Green Tea Serum", "category": "serum", "usage_time": "both",
     "skin_types": ["oily", "combination", "balanced"], "concerns": ["redness", "oiliness", "sensitivity"],
     "description": "A light antioxidant serum that feels fresh and non-sticky.",
     "uses": "Calms the look of redness and shine on oily-to-normal skin.",
     "how_to_use": "Apply after toner and before moisturizer.",
     "cautions": None, "ingredients": ["Green Tea Extract", "Niacinamide", "Allantoin"]},

    # ---------------- Moisturizers ----------------
    {"name": "Oil-Free Gel Moisturizer", "category": "moisturizer", "usage_time": "both",
     "skin_types": ["oily", "combination"], "concerns": ["oiliness", "acne", "dryness"],
     "description": "A bouncy water-gel moisturizer that does not feel greasy.",
     "uses": "Daily hydration for oily skin that still needs moisture.",
     "how_to_use": "Apply a thin layer to face and neck, morning and night.",
     "cautions": None, "ingredients": ["Hyaluronic Acid", "Glycerin", "Niacinamide"]},
    {"name": "Lightweight Gel-Cream Moisturizer", "category": "moisturizer", "usage_time": "both",
     "skin_types": ["combination", "balanced"], "concerns": ["dryness", "oiliness", "dullness"],
     "description": "Between a gel and a cream, good for mixed skin.",
     "uses": "Everyday hydration without heaviness.",
     "how_to_use": "Apply after serums, morning and night.",
     "cautions": None, "ingredients": ["Glycerin", "Squalane", "Panthenol (Vitamin B5)"]},
    {"name": "Rich Nourishing Cream", "category": "moisturizer", "usage_time": "night",
     "skin_types": ["dry"], "concerns": ["dryness", "dullness"],
     "description": "A thicker cream for dry or flaky skin.",
     "uses": "Seals in moisture overnight for dry skin.",
     "how_to_use": "Apply as the last step of the night routine.",
     "cautions": "May feel heavy on oily or breakout-prone skin.",
     "ingredients": ["Shea Butter", "Glycerin", "Ceramides", "Squalane"]},
    {"name": "Ceramide Barrier Cream", "category": "moisturizer", "usage_time": "both",
     "skin_types": ["dry", "balanced", "combination"], "concerns": ["dryness", "sensitivity", "redness"],
     "description": "A fragrance-free barrier cream for dry, tight or easily irritated skin.",
     "uses": "Supports the skin barrier and reduces dryness.",
     "how_to_use": "Apply to face and neck morning and night.",
     "cautions": None, "ingredients": ["Ceramides", "Glycerin", "Panthenol (Vitamin B5)", "Allantoin"]},
    {"name": "Light Daily Lotion", "category": "moisturizer", "usage_time": "both",
     "skin_types": ["balanced", "combination"], "concerns": ["dryness", "dullness"],
     "description": "A simple everyday lotion for normal skin.",
     "uses": "Basic daily moisture.",
     "how_to_use": "Apply after cleansing and serum.",
     "cautions": None, "ingredients": ["Glycerin", "Dimethicone", "Squalane"]},
    {"name": "Soothing Aloe Gel-Cream", "category": "moisturizer", "usage_time": "both",
     "skin_types": ["oily", "combination", "balanced"], "concerns": ["redness", "sensitivity", "oiliness"],
     "description": "A cooling aloe-based moisturizer.",
     "uses": "Light hydration for skin that looks red or feels warm.",
     "how_to_use": "Apply a thin layer morning and night.",
     "cautions": "Patch test if you are allergic to aloe.",
     "ingredients": ["Aloe Vera", "Centella Asiatica", "Glycerin"]},

    # ---------------- Sunscreens ----------------
    {"name": "Mineral Sunscreen SPF 50", "category": "sunscreen", "usage_time": "morning",
     "skin_types": ALL, "concerns": ["sensitivity", "redness"],
     "description": "A zinc-oxide sunscreen that sits on top of the skin.",
     "uses": "Daily sun protection, suited to sensitive skin.",
     "how_to_use": "Apply generously as the last morning step. Reapply every 2 hours outdoors.",
     "cautions": "May leave a slight white cast.", "ingredients": ["Zinc Oxide", "Titanium Dioxide"]},
    {"name": "Lightweight Gel Sunscreen SPF 50", "category": "sunscreen", "usage_time": "morning",
     "skin_types": ["oily", "combination"], "concerns": ["oiliness", "acne"],
     "description": "A watery sunscreen that dries with a natural finish.",
     "uses": "Daily sun protection for oily skin.",
     "how_to_use": "Apply generously 15 minutes before sun exposure. Reapply every 2 hours.",
     "cautions": "Can sting around the eyes for some people.",
     "ingredients": ["Chemical UV Filters", "Glycerin", "Niacinamide"]},
    {"name": "Hydrating Sunscreen SPF 30 Cream", "category": "sunscreen", "usage_time": "morning",
     "skin_types": ["dry", "balanced"], "concerns": ["dryness", "dullness"],
     "description": "A creamy sunscreen that moisturizes while protecting.",
     "uses": "Daily sun protection for dry skin.",
     "how_to_use": "Apply generously as the last morning step. Reapply every 2 hours outdoors.",
     "cautions": None, "ingredients": ["Zinc Oxide", "Hyaluronic Acid", "Squalane"]},
    {"name": "Matte Fluid Sunscreen SPF 50", "category": "sunscreen", "usage_time": "morning",
     "skin_types": ["oily", "combination"], "concerns": ["oiliness"],
     "description": "A fluid sunscreen with a shine-free finish.",
     "uses": "Daily sun protection for oily skin that gets shiny during the day.",
     "how_to_use": "Apply generously, reapply every 2 hours outdoors.",
     "cautions": None, "ingredients": ["Chemical UV Filters", "Kaolin Clay", "Zinc PCA"]},

    # ---------------- Exfoliants ----------------
    {"name": "Mild Lactic Acid Exfoliant", "category": "exfoliant", "usage_time": "night",
     "skin_types": ["dry", "balanced", "combination"], "concerns": ["texture", "dullness", "dryness"],
     "description": "A gentle AHA exfoliant that also helps hydrate.",
     "uses": "Smooths rough texture and brightens a dull look.",
     "how_to_use": "Use once or twice a week at night after cleansing. Moisturize after.",
     "cautions": "Use daily sunscreen. Stop if skin burns or peels.",
     "ingredients": ["Lactic Acid", "Glycerin", "Allantoin"]},
    {"name": "Glycolic Acid Exfoliating Pads", "category": "exfoliant", "usage_time": "night",
     "skin_types": ["balanced", "combination", "oily"], "concerns": ["texture", "dullness"],
     "description": "Pre-soaked pads with a low level of glycolic acid.",
     "uses": "Weekly exfoliation for rough texture and uneven tone.",
     "how_to_use": "Swipe once over clean skin at night, once or twice a week.",
     "cautions": "Can irritate. Not with retinol on the same night. Use sunscreen daily.",
     "ingredients": ["Glycolic Acid", "Aloe Vera"]},
    {"name": "2% BHA Liquid Exfoliant", "category": "exfoliant", "usage_time": "night",
     "skin_types": ["oily", "combination"], "concerns": ["acne", "oiliness", "texture"],
     "description": "A leave-on salicylic acid liquid for blackheads and clogged pores.",
     "uses": "Exfoliates inside pores on oily, breakout-prone skin.",
     "how_to_use": "Apply to clean skin 2-3 times a week at night.",
     "cautions": "Can dry or sting. Not recommended during pregnancy without medical advice. Use sunscreen daily.",
     "ingredients": ["Salicylic Acid", "Green Tea Extract"]},

    # ---------------- Masks ----------------
    {"name": "Clay Purifying Mask", "category": "mask", "usage_time": "night",
     "skin_types": ["oily", "combination"], "concerns": ["oiliness", "acne"],
     "description": "A clay mask that absorbs excess oil.",
     "uses": "Weekly deep cleanse for oily skin.",
     "how_to_use": "Apply a thin layer for 5-10 minutes once a week, rinse before it fully dries.",
     "cautions": "Do not leave on until cracked and tight.", "ingredients": ["Kaolin Clay", "Glycerin"]},
    {"name": "Overnight Hydrating Mask", "category": "mask", "usage_time": "night",
     "skin_types": ["dry", "balanced"], "concerns": ["dryness", "dullness"],
     "description": "A leave-on gel-cream mask for extra moisture.",
     "uses": "Boosts hydration for dry or tired-looking skin.",
     "how_to_use": "Apply as the last step 2-3 times a week and leave overnight.",
     "cautions": None, "ingredients": ["Hyaluronic Acid", "Ceramides", "Squalane"]},

    # ---------------- Spot treatments ----------------
    {"name": "Benzoyl Peroxide 2.5% Spot Gel", "category": "spot treatment", "usage_time": "night",
     "skin_types": ["oily", "combination"], "concerns": ["acne"],
     "description": "A low-strength spot gel for active pimples.",
     "uses": "Dabbed onto individual pimples.",
     "how_to_use": "Apply a thin layer only on pimples once daily at night.",
     "cautions": "Can dry, peel and bleach towels or pillowcases. Do not apply to whole face at first.",
     "ingredients": ["Benzoyl Peroxide"]},
    {"name": "Tea Tree & Zinc Spot Gel", "category": "spot treatment", "usage_time": "night",
     "skin_types": ["oily", "combination"], "concerns": ["acne"],
     "description": "A natural-leaning spot gel with tea tree oil.",
     "uses": "Dabbed onto small breakouts.",
     "how_to_use": "Dab on pimples at night, no more than once or twice daily.",
     "cautions": "Not for sensitive skin. Patch test first.",
     "ingredients": ["Tea Tree Oil", "Zinc PCA"]},
]
# ---------------------------------------------------------------------
# APP METADATA, VALIDATION, AND PROFILE-BASED RECOMMENDATIONS
# ---------------------------------------------------------------------
# Keep the catalog generic. These records are examples, not verified retail
# products, and should never be presented as medical diagnoses or prescriptions.

ACTIVE_INGREDIENTS = {
    "Salicylic Acid", "Glycolic Acid", "Lactic Acid", "Benzoyl Peroxide",
    "Retinol", "Vitamin C (Ascorbic Acid)", "Tea Tree Oil", "Alcohol Denat.",
}

# Extra caution for pregnancy-related profiles. This is a conservative app
# rule, not a substitute for clinician/pharmacist advice.
PREGNANCY_CAUTION_INGREDIENTS = {
    "Retinol", "Salicylic Acid", "Benzoyl Peroxide", "Glycolic Acid",
    "Lactic Acid", "Azelaic Acid", "Vitamin C (Ascorbic Acid)",
}


def _add_metadata() -> None:
    """Attach consistent metadata expected by the API/seed layer."""
    for item in INGREDIENTS:
        item.setdefault("id", item["name"].lower().replace(" ", "-").replace("(", "").replace(")", ""))
        item["is_sample_data"] = True
        item["source"] = SOURCE
    for item in PRODUCTS:
        item.setdefault("id", item["name"].lower().replace(" ", "-").replace("%", "pct"))
        item["brand"] = BRAND
        item["is_sample_data"] = True
        item["source"] = SOURCE
        item.setdefault("cautions", None)


_add_metadata()


def validate_catalog() -> list[str]:
    """Return validation errors; an empty list means the catalog is consistent."""
    errors: list[str] = []
    allowed_skin_types = {"dry", "oily", "combination", "balanced"}
    allowed_concerns = {
        "acne", "dryness", "redness", "texture", "oiliness",
        "sensitivity", "dullness",
    }
    ingredient_names = {x.get("name") for x in INGREDIENTS}
    for kind, records in (("ingredient", INGREDIENTS), ("product", PRODUCTS)):
        seen: set[str] = set()
        for index, item in enumerate(records):
            name = item.get("name")
            if not name:
                errors.append(f"{kind}[{index}] is missing name")
            elif name in seen:
                errors.append(f"duplicate {kind} name: {name}")
            seen.add(name)
            for skin_type in item.get("skin_types", []):
                if skin_type not in allowed_skin_types:
                    errors.append(f"{kind} {name}: unsupported skin type {skin_type}")
            for concern in item.get("concerns", []):
                if concern not in allowed_concerns:
                    errors.append(f"{kind} {name}: unsupported concern {concern}")
            if item.get("is_sample_data") is not True or not item.get("source"):
                errors.append(f"{kind} {name}: sample-data/source metadata missing")
            if kind == "product":
                for ingredient in item.get("ingredients", []):
                    if ingredient not in ingredient_names:
                        errors.append(f"product {name}: unknown ingredient {ingredient}")
    return errors


def recommend_products(profile: dict, limit_per_category: int = 2) -> list[dict]:
    """Rank generic product archetypes for an assessment profile.

    Expected profile keys:
      skin_type: dry | oily | combination | balanced
      concerns: list[str]
      sensitive_skin: bool (optional)
      pregnant_or_trying: bool (optional; conservative caution filter)
      excluded_ingredients: list[str] (optional; user-reported exclusions)

    Results include a score and reasons so the UI can explain why an item matched.
    """
    skin_type = str(profile.get("skin_type", "balanced")).strip().lower()
    if skin_type not in {"dry", "oily", "combination", "balanced"}:
        skin_type = "balanced"
    concerns = set(profile.get("concerns") or []) & {
        "acne", "dryness", "redness", "texture", "oiliness",
        "sensitivity", "dullness",
    }
    sensitive = bool(profile.get("sensitive_skin")) or "sensitivity" in concerns
    pregnancy_caution = bool(profile.get("pregnant_or_trying"))
    excluded = {str(x).strip().casefold() for x in (profile.get("excluded_ingredients") or [])}

    ranked: list[dict] = []
    for product in PRODUCTS:
        ingredients = product.get("ingredients", [])
        ingredient_folded = {x.casefold() for x in ingredients}
        if excluded & ingredient_folded:
            continue
        if sensitive and any(x in ACTIVE_INGREDIENTS or x == "Fragrance" for x in ingredients):
            # Prefer gentler archetypes; this is a cautious heuristic, not a guarantee.
            continue
        if pregnancy_caution and any(x in PREGNANCY_CAUTION_INGREDIENTS for x in ingredients):
            continue
        if skin_type not in product.get("skin_types", []):
            continue

        overlap = concerns.intersection(product.get("concerns", []))
        score = 2 + (3 if overlap else 0) + len(overlap) * 2
        reasons = [f"listed for {skin_type} skin"]
        if overlap:
            reasons.append("matches concerns: " + ", ".join(sorted(overlap)))
        if sensitive:
            reasons.append("passed the app's conservative sensitive-skin filter")
        if pregnancy_caution:
            reasons.append("passed the app's conservative pregnancy-caution filter")
        ranked.append({**product, "score": score, "match_reasons": reasons})

    ranked.sort(key=lambda x: (-x["score"], x["category"], x["name"]))
    # Keep recommendations varied and avoid suggesting a long list of actives.
    results: list[dict] = []
    category_counts: dict[str, int] = {}
    active_categories = {"exfoliant", "spot treatment"}
    for item in ranked:
        category = item["category"]
        if category_counts.get(category, 0) >= max(1, limit_per_category):
            continue
        if category in active_categories and category_counts.get(category, 0) >= 1:
            continue
        category_counts[category] = category_counts.get(category, 0) + 1
        results.append(item)
    return results


def build_basic_routine(profile: dict) -> dict[str, list[dict]]:
    """Build a small AM/PM suggestion using ranked sample archetypes."""
    recommendations = recommend_products(profile, limit_per_category=2)
    by_category: dict[str, list[dict]] = {}
    for item in recommendations:
        by_category.setdefault(item["category"], []).append(item)

    def first(category: str) -> list[dict]:
        items = by_category.get(category, [])
        return items[:1]

    morning = first("cleanser") + first("serum") + first("moisturizer") + first("sunscreen")
    evening = first("cleanser") + first("serum") + first("moisturizer")
    return {"morning": morning, "evening": evening, "all_matches": recommendations}


if __name__ == "__main__":
    problems = validate_catalog()
    if problems:
        print("Catalog validation failed:")
        print("\n".join(f"- {problem}" for problem in problems))
    else:
        print(f"Catalog OK: {len(INGREDIENTS)} ingredients, {len(PRODUCTS)} products")
        demo = recommend_products({"skin_type": "oily", "concerns": ["acne", "oiliness"]})
        print("Demo recommendations:")
        for item in demo[:8]:
            print(f"- {item['name']} ({item['category']}) — score {item['score']}")
