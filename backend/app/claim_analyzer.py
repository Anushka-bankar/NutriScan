import re


FSSAI_CLAIMS_REFERENCE = {
    "title": (
        "FSSAI Food Safety and Standards (Advertising and Claims) Regulations, "
        "2018 — 2022 compendium"
    ),
    "url": (
        "https://www.fssai.gov.in/docs/food-law/regulations/"
        "Compendium_Advertising_Claims_Regulations_14_12_2022.pdf"
    ),
}

_SOLID_PRODUCT_CATEGORIES = {
    "grains_cereals",
    "snacks",
    "meat_poultry",
    "seafood",
    "plant_protein",
    "fruits_vegetables",
    "bakery",
}

_CLAIM_PATTERNS = [
    ("no_added_sugar", r"\bno[\s-]+added\s+sugars?\b", "Nutrition claim"),
    ("sugar_free", r"\bsugar[\s-]*free\b", "Nutrition claim"),
    ("low_sugar", r"\blow\s+sugars?\b", "Nutrition claim"),
    ("high_protein", r"\bhigh\s+protein\b", "Nutrition claim"),
    ("source_of_protein", r"\b(?:source\s+of\s+protein|protein\s+source)\b", "Nutrition claim"),
    ("low_fat", r"\blow\s+fat\b", "Nutrition claim"),
    ("fat_free", r"\bfat[\s-]*free\b", "Nutrition claim"),
    ("zero_cholesterol", r"\b(?:zero|0)\s+cholesterol\b|\bcholesterol[\s-]*free\b", "Nutrition claim"),
    ("high_fibre", r"\bhigh\s+(?:fibre|fiber)\b", "Nutrition claim"),
    ("low_sodium", r"\blow\s+sodium\b", "Nutrition claim"),
    ("low_carb", r"\blow\s+carb(?:ohydrate)?s?\b", "Nutrition claim"),
    ("reduced_sugar", r"\breduced\s+sugars?\b", "Nutrition claim"),
    ("gluten_free", r"\bgluten[\s-]*free\b", "Dietary claim"),
    ("organic", r"\borganic\b", "Certification claim"),
    ("natural", r"\b(?:100\s*%\s*|all[\s-]+)?natural\b", "Marketing claim"),
    ("no_preservatives", r"\bno\s+preservatives?\b|\bpreservative[\s-]*free\b", "Marketing claim"),
    ("no_artificial_colours", r"\bno\s+artificial\s+(?:colou?rs?|flavou?rs?)\b", "Marketing claim"),
    ("non_gmo", r"\bnon[\s-]?gmo\b", "Marketing claim"),
    ("vegan", r"\bvegan\b", "Dietary claim"),
    ("keto", r"\bketo(?:genic)?(?:[\s-]+friendly)?\b", "Marketing claim"),
    ("immunity", r"\b(?:boosts?|supports?)\s+(?:the\s+)?immune\s+system\b", "Health-related marketing claim"),
    ("detox", r"\bdetox(?:ifies|ification)?\b", "Health-related marketing claim"),
    ("superfood", r"\bsuper[\s-]?food\b", "Marketing claim"),
    ("clinically_proven", r"\bclinically\s+proven\b", "Health-related marketing claim"),
    ("doctor_recommended", r"\bdoctor[\s-]+recommended\b", "Health-related marketing claim"),
]

_ADDED_SUGAR_PATTERN = re.compile(
    r"\b(?:sugar|sucrose|dextrose|glucose|fructose|maltose|"
    r"glucose syrup|corn syrup|invert syrup|honey|jaggery|molasses|"
    r"maple syrup|agave syrup)\b",
    re.IGNORECASE,
)
_PRESERVATIVE_INGREDIENT_PATTERN = re.compile(
    r"\b(?:sodium benzoate|potassium sorbate|calcium propionate|"
    r"sodium nitrite|potassium metabisulfite|sodium metabisulfite|"
    r"e\s?2(?:00|01|02|03|10|11|12|20|21|22|23|24))\b",
    re.IGNORECASE,
)
_GLUTEN_INGREDIENT_PATTERN = re.compile(
    r"\b(?:wheat|barley|rye|triticale|malt extract|malt flour)\b",
    re.IGNORECASE,
)
_STATUS_LABELS = {
    "supported": "Appears supported",
    "potentially_inconsistent": "Potentially inconsistent",
    "unverifiable": "Unable to verify",
}


def detect_food_claims(text, include_manual_unknown=False):
    claims = []
    for code, pattern, category in _CLAIM_PATTERNS:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            claims.append(
                {
                    "code": code,
                    "text": match.group(0),
                    "category": category,
                    "start": match.start(),
                    "end": match.end(),
                }
            )
    claims.sort(key=lambda claim: (claim["start"], claim["end"]))

    non_overlapping = []
    for claim in claims:
        if non_overlapping and claim["start"] < non_overlapping[-1]["end"]:
            continue
        non_overlapping.append(claim)

    if include_manual_unknown:
        for match in re.finditer(r"[^,\n;]+", text):
            segment = match.group(0).strip()
            if not segment:
                continue
            start = match.start() + len(match.group(0)) - len(match.group(0).lstrip())
            end = start + len(segment)
            if not any(
                claim["start"] < end and claim["end"] > start
                for claim in non_overlapping
            ):
                non_overlapping.append(
                    {
                        "code": "unrecognized_claim",
                        "text": segment,
                        "category": "Unclassified claim",
                        "start": start,
                        "end": end,
                    }
                )
        non_overlapping.sort(key=lambda claim: (claim["start"], claim["end"]))
    return non_overlapping


def _nutrition_fact(product, field, label, unit=None):
    raw_value = getattr(product, field, None)
    if raw_value is None:
        value = None
    else:
        try:
            value = float(raw_value)
        except (TypeError, ValueError):
            value = None
    return {
        "field": field,
        "label": label,
        "value": value,
        "unit": unit or ("mg" if field.endswith("_mg") else "g"),
        "basis": "per 100 g",
    }


def _claim_result(claim, status, explanation, evidence=None, criteria=None, references=None):
    return {
        **claim,
        "status": status,
        "status_label": _STATUS_LABELS[status],
        "explanation": explanation,
        "evidence": evidence or [],
        "criteria": criteria,
        "references": references or [],
    }


def _check_mass_threshold(claim, product, field, nutrient_label, threshold, claim_label):
    fact = _nutrition_fact(product, field, nutrient_label)
    if fact["value"] is None:
        return _claim_result(
            claim,
            "unverifiable",
            f"The product's {nutrient_label.lower()} value is unavailable, so this claim cannot be checked.",
            evidence=[fact],
        )

    category = getattr(product, "category", None)
    if category == "beverages":
        return _claim_result(
            claim,
            "unverifiable",
            "This product is categorized as a beverage, but saved nutrition is per 100 g. "
            "The applicable FSSAI comparison is per 100 ml, and no density conversion is assumed.",
            evidence=[fact],
            criteria=claim_label,
            references=[FSSAI_CLAIMS_REFERENCE],
        )
    if category not in _SOLID_PRODUCT_CATEGORIES:
        return _claim_result(
            claim,
            "unverifiable",
            "The saved category does not establish that this product is a solid, so a "
            "per-100 g threshold cannot safely be selected.",
            evidence=[fact],
            criteria=claim_label,
            references=[FSSAI_CLAIMS_REFERENCE],
        )

    supported = fact["value"] <= threshold
    status = "supported" if supported else "potentially_inconsistent"
    observed = f"{fact['value']:g} g per 100 g"
    explanation = (
        f"Saved {nutrient_label.lower()} is {observed}; the FSSAI reference criterion "
        f"for this claim is no more than {threshold:g} g per 100 g for solids. "
        "This is a preliminary check of unverified product data, not official verification."
        if supported
        else f"Saved {nutrient_label.lower()} is {observed}, above the FSSAI reference "
        f"criterion of {threshold:g} g per 100 g for solids. This is a potential "
        "inconsistency in the saved data, not a finding of legal non-compliance."
    )
    return _claim_result(
        claim,
        status,
        explanation,
        evidence=[fact],
        criteria=f"Not more than {threshold:g} g per 100 g for solids",
        references=[FSSAI_CLAIMS_REFERENCE],
    )


def _verify_claim(claim, product):
    ingredients = getattr(product, "ingredients", None)
    ingredients = ingredients if isinstance(ingredients, str) else ""
    sugar_fact = _nutrition_fact(product, "sugars_g", "Total sugar")
    fat_fact = _nutrition_fact(product, "total_fat_g", "Total fat")

    if claim["code"] == "sugar_free":
        return _check_mass_threshold(
            claim, product, "sugars_g", "Total sugar", 0.5,
            "Sugar-free: no more than 0.5 g sugars per 100 g solid food or 100 ml liquid.",
        )
    if claim["code"] == "low_sugar":
        return _check_mass_threshold(
            claim, product, "sugars_g", "Total sugar", 5,
            "Low sugar: no more than 5 g sugars per 100 g solid food or 2.5 g per 100 ml liquid.",
        )
    if claim["code"] == "low_fat":
        return _check_mass_threshold(
            claim, product, "total_fat_g", "Total fat", 3,
            "Low fat: no more than 3 g fat per 100 g solid food or 1.5 g per 100 ml liquid.",
        )
    if claim["code"] == "fat_free":
        return _check_mass_threshold(
            claim, product, "total_fat_g", "Total fat", 0.5,
            "Fat-free: no more than 0.5 g fat per 100 g solid food or 100 ml liquid.",
        )
    if claim["code"] == "no_added_sugar":
        if not ingredients.strip():
            return _claim_result(
                claim,
                "unverifiable",
                "No ingredient list is saved. Total sugar alone cannot distinguish added sugars from naturally occurring sugars.",
                evidence=[sugar_fact],
            )
        added_sugar = _ADDED_SUGAR_PATTERN.search(ingredients)
        if added_sugar:
            return _claim_result(
                claim,
                "potentially_inconsistent",
                f"The saved ingredient list includes “{added_sugar.group(0)}”, a possible added-sugar source. "
                "Check the complete package label; this is not a legal finding.",
                evidence=[
                    {"label": "Ingredient-list match", "value": added_sugar.group(0)},
                    sugar_fact,
                ],
            )
        return _claim_result(
            claim,
            "unverifiable",
            "No recognized added-sugar term was found in the saved ingredient list, but "
            "the list may be incomplete and total sugars may occur naturally.",
            evidence=[{"label": "Saved ingredients", "value": ingredients}, sugar_fact],
        )
    if claim["code"] == "gluten_free":
        gluten_match = _GLUTEN_INGREDIENT_PATTERN.search(ingredients)
        if gluten_match:
            return _claim_result(
                claim,
                "potentially_inconsistent",
                f"The saved ingredient list includes “{gluten_match.group(0)}”. "
                "The ingredient list alone cannot establish gluten content or legal compliance.",
                evidence=[{"label": "Ingredient-list match", "value": gluten_match.group(0)}],
            )
        return _claim_result(
            claim,
            "unverifiable",
            "No listed gluten-containing grain was detected, but this does not verify "
            "gluten concentration or manufacturing cross-contact.",
            evidence=[{"label": "Saved ingredients", "value": ingredients or None}],
        )
    if claim["code"] == "no_preservatives":
        preservative = _PRESERVATIVE_INGREDIENT_PATTERN.search(ingredients)
        if preservative:
            return _claim_result(
                claim,
                "potentially_inconsistent",
                f"The saved ingredient list includes “{preservative.group(0)}”, a recognized preservative term. "
                "Confirm against the package; this is not a legal finding.",
                evidence=[{"label": "Ingredient-list match", "value": preservative.group(0)}],
            )

    nutrient_fields = {
        "high_protein": ("protein_g", "Protein"),
        "source_of_protein": ("protein_g", "Protein"),
        "high_fibre": ("fibre_g", "Fibre"),
        "zero_cholesterol": ("cholesterol_mg", "Cholesterol"),
        "low_sodium": ("sodium_mg", "Sodium"),
        "low_carb": ("carbohydrates_g", "Carbohydrates"),
        "reduced_sugar": ("sugars_g", "Total sugar"),
    }
    if claim["code"] in nutrient_fields:
        field, label = nutrient_fields[claim["code"]]
        evidence = [_nutrition_fact(product, field, label)]
        return _claim_result(
            claim,
            "unverifiable",
            "Available product information is shown, but NutriScan does not have a "
            "verified applicable criterion and/or the required measurement to assess this claim.",
            evidence=evidence,
            references=[FSSAI_CLAIMS_REFERENCE] if label else [],
        )

    evidence = []
    if ingredients:
        evidence.append({"label": "Saved ingredients", "value": ingredients})
    for field, label in (
        ("protein_g", "Protein"),
        ("sugars_g", "Total sugar"),
        ("total_fat_g", "Total fat"),
        ("fibre_g", "Fibre"),
    ):
        fact = _nutrition_fact(product, field, label)
        if fact["value"] is not None:
            evidence.append(fact)
    return _claim_result(
        claim,
        "unverifiable",
        "No reliable verification rule or required supporting evidence is available for this claim.",
        evidence=evidence,
    )


def analyze_food_claims(claim_text, product, dietary_preferences=None, manual_input=False):
    claims = detect_food_claims(claim_text, include_manual_unknown=manual_input)
    analyzed_claims = [_verify_claim(claim, product) for claim in claims]
    preferences = set(
        preference
        for preference in (dietary_preferences or [])
        if isinstance(preference, str)
    )
    personal_context = []
    if "gluten_free" in preferences and any(
        claim["code"] == "gluten_free" for claim in analyzed_claims
    ):
        personal_context.append(
            "Your profile includes a gluten-free preference. This preliminary label check "
            "cannot assess gluten concentration, cross-contact, or individual suitability."
        )
    if "vegan" in preferences and any(
        claim["code"] == "vegan" for claim in analyzed_claims
    ):
        personal_context.append(
            "Your profile includes a vegan preference. The saved ingredient list may be "
            "incomplete and does not verify manufacturing or certification."
        )

    counts = {
        status: sum(claim["status"] == status for claim in analyzed_claims)
        for status in _STATUS_LABELS
    }
    return {
        "claims": analyzed_claims,
        "summary": {
            "claim_count": len(analyzed_claims),
            "supported_count": counts["supported"],
            "potentially_inconsistent_count": counts["potentially_inconsistent"],
            "unverifiable_count": counts["unverifiable"],
        },
        "personal_context": personal_context,
        "disclaimer": (
            "Preliminary comparison with saved product information. Product facts may be "
            "user-entered, OCR-extracted, or community-sourced and are not independently "
            "verified. This is not official FSSAI verification, a legal compliance finding, "
            "or medical advice."
        ),
    }
