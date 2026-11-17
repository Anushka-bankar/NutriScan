import re


REFERENCES = {
    "fda_additives": {
        "title": "FDA: Food Additives and GRAS Ingredients",
        "url": "https://www.fda.gov/food/food-ingredients-packaging/food-additives-and-gras-ingredients-information-consumers",
    },
    "fda_allergens": {
        "title": "FDA: Food Allergies and Major Food Allergens",
        "url": "https://www.fda.gov/food/nutrition-food-labeling-and-critical-foods/food-allergies",
    },
    "fda_sweeteners": {
        "title": "FDA: Aspartame and Other Sweeteners",
        "url": "https://www.fda.gov/food/food-additives-petitions/aspartame-and-other-sweeteners-food",
    },
    "fda_colors": {
        "title": "FDA: Color Additives",
        "url": "https://www.fda.gov/industry/color-additives",
    },
}

_KNOWLEDGE = [
    {
        "key": "sugar",
        "aliases": ["sugar", "sucrose", "cane sugar", "beet sugar"],
        "category": "sweetener",
        "what_it_is": "A common food sugar; sucrose is the main sugar in table sugar.",
        "purpose": "Used to sweeten foods and can also affect texture and browning.",
        "flags": set(),
        "references": ["fda_additives"],
    },
    {
        "key": "soy_lecithin",
        "aliases": ["soy lecithin", "soya lecithin"],
        "category": "emulsifier",
        "what_it_is": "A soy-derived phospholipid mixture used as a food ingredient.",
        "purpose": "Helps ingredients such as oil and water mix and remain evenly distributed.",
        "flags": {"major_allergen"},
        "allergen": "soybeans",
        "references": ["fda_allergens", "fda_additives"],
    },
    {
        "key": "honey",
        "aliases": ["honey"],
        "category": "sweetener",
        "what_it_is": "A sweet food produced by honeybees from nectar.",
        "purpose": "Used as a sweetener and for flavour.",
        "flags": {"animal_derived"},
        "references": ["fda_additives"],
    },
    {
        "key": "salt",
        "aliases": ["salt", "sodium chloride"],
        "category": "general_food_ingredient",
        "what_it_is": "Salt is primarily sodium chloride.",
        "purpose": "Used for flavour; it can also help preserve some foods.",
        "flags": set(),
        "references": ["fda_additives"],
    },
    {
        "key": "water",
        "aliases": ["water"],
        "category": "general_food_ingredient",
        "what_it_is": "Water included as a food ingredient.",
        "purpose": "Can dissolve, carry, or adjust the consistency of other ingredients.",
        "flags": set(),
        "references": [],
    },
    {
        "key": "oats",
        "aliases": ["oats", "oat flour", "rolled oats"],
        "category": "general_food_ingredient",
        "what_it_is": "A cereal grain ingredient made from oats.",
        "purpose": "Used as a grain, source of texture, or base ingredient.",
        "flags": set(),
        "references": [],
    },
    {
        "key": "cocoa",
        "aliases": ["cocoa powder", "cocoa", "cacao"],
        "category": "general_food_ingredient",
        "what_it_is": "A cocoa-bean ingredient used for its characteristic flavour and colour.",
        "purpose": "Used to provide chocolate flavour and colour.",
        "flags": set(),
        "references": [],
    },
    {
        "key": "sodium_benzoate",
        "aliases": ["sodium benzoate", "e211"],
        "category": "preservative",
        "what_it_is": "A benzoate salt used as a food additive.",
        "purpose": "Used as a preservative to help maintain food quality.",
        "flags": set(),
        "references": ["fda_additives"],
    },
    {
        "key": "potassium_sorbate",
        "aliases": ["potassium sorbate", "e202"],
        "category": "preservative",
        "what_it_is": "A sorbate salt used as a food additive.",
        "purpose": "Used as a preservative to help maintain food quality.",
        "flags": set(),
        "references": ["fda_additives"],
    },
    {
        "key": "citric_acid",
        "aliases": ["citric acid", "e330"],
        "category": "other_additive",
        "what_it_is": "An acid used in foods.",
        "purpose": "Commonly used to adjust acidity and flavour.",
        "flags": set(),
        "references": ["fda_additives"],
    },
    {
        "key": "lecithin",
        "aliases": ["sunflower lecithin", "lecithin", "e322"],
        "category": "emulsifier",
        "what_it_is": "A mixture of phospholipids used as a food ingredient; its source varies.",
        "purpose": "Helps ingredients such as oil and water mix and remain evenly distributed.",
        "flags": set(),
        "references": ["fda_additives"],
    },
    {
        "key": "xanthan_gum",
        "aliases": ["xanthan gum", "e415"],
        "category": "stabilizer",
        "what_it_is": "A food gum used to modify texture.",
        "purpose": "Used as a thickener or stabilizer.",
        "flags": set(),
        "references": ["fda_additives"],
    },
    {
        "key": "pectin",
        "aliases": ["pectin", "e440"],
        "category": "stabilizer",
        "what_it_is": "A plant-derived carbohydrate found in fruit cell walls.",
        "purpose": "Used as a gelling agent or thickener.",
        "flags": set(),
        "references": ["fda_additives"],
    },
    {
        "key": "gelatin",
        "aliases": ["gelatin", "gelatine", "e441"],
        "category": "stabilizer",
        "what_it_is": "A gelling ingredient made from animal-derived collagen.",
        "purpose": "Used to form or stabilize gels and textures.",
        "flags": {"animal_derived", "source_uncertain"},
        "references": ["fda_additives"],
    },
    {
        "key": "carmine",
        "aliases": ["carmine", "cochineal", "cochineal extract", "e120"],
        "category": "colouring_agent",
        "what_it_is": "A red colour additive made from cochineal insects.",
        "purpose": "Used to add red colour to foods.",
        "flags": {"animal_derived"},
        "references": ["fda_colors"],
    },
    {
        "key": "annatto",
        "aliases": ["annatto", "annatto extract", "e160b"],
        "category": "colouring_agent",
        "what_it_is": "A colour ingredient derived from annatto seeds.",
        "purpose": "Used to add yellow-to-orange colour to foods.",
        "flags": set(),
        "references": ["fda_colors"],
    },
    {
        "key": "tartrazine",
        "aliases": ["tartrazine", "yellow 5", "fd&c yellow no. 5", "e102"],
        "category": "colouring_agent",
        "what_it_is": "A synthetic food colour also known as Yellow 5.",
        "purpose": "Used to add yellow colour to foods.",
        "flags": set(),
        "references": ["fda_colors"],
    },
    {
        "key": "aspartame",
        "aliases": ["aspartame", "e951"],
        "category": "sweetener",
        "what_it_is": "A high-intensity sweetener.",
        "purpose": "Used to provide sweetness, generally in smaller amounts than sugar.",
        "flags": set(),
        "health_considerations": (
            "The FDA says people with phenylketonuria (PKU) should avoid or restrict "
            "aspartame. The ingredient list alone cannot assess an individual's needs."
        ),
        "references": ["fda_sweeteners"],
    },
    {
        "key": "sucralose",
        "aliases": ["sucralose", "e955"],
        "category": "sweetener",
        "what_it_is": "A high-intensity sweetener.",
        "purpose": "Used to provide sweetness in small amounts.",
        "flags": set(),
        "references": ["fda_sweeteners"],
    },
    {
        "key": "steviol_glycosides",
        "aliases": ["stevia", "steviol glycosides", "rebaudioside a", "e960"],
        "category": "sweetener",
        "what_it_is": "Sweet-tasting compounds derived from the stevia plant.",
        "purpose": "Used to provide sweetness in small amounts.",
        "flags": set(),
        "references": ["fda_sweeteners"],
    },
    {
        "key": "milk",
        "aliases": [
            "milk powder", "milk solids", "skimmed milk", "whole milk",
            "milk protein", "milk sugar", "buttermilk powder", "lactose", "milk",
        ],
        "category": "general_food_ingredient",
        "what_it_is": "A milk-derived food ingredient.",
        "purpose": "Can provide flavour, protein, or texture, depending on the product.",
        "flags": {"dairy", "major_allergen"},
        "allergen": "milk",
        "references": ["fda_allergens"],
    },
    {
        "key": "plant_milk",
        "aliases": ["coconut milk", "oat milk", "rice milk", "plant milk"],
        "category": "general_food_ingredient",
        "what_it_is": "A plant-based drink or ingredient; the plant source should be checked on the label.",
        "purpose": "Used as a liquid ingredient or an alternative to dairy milk.",
        "flags": set(),
        "references": [],
    },
    {
        "key": "soy_milk",
        "aliases": ["soy milk", "soya milk"],
        "category": "general_food_ingredient",
        "what_it_is": "A plant-based drink made from soybeans.",
        "purpose": "Used as a liquid ingredient or an alternative to dairy milk.",
        "flags": {"major_allergen"},
        "allergen": "soybeans",
        "references": ["fda_allergens"],
    },
    {
        "key": "almond_milk",
        "aliases": ["almond milk"],
        "category": "general_food_ingredient",
        "what_it_is": "A plant-based drink made from almonds.",
        "purpose": "Used as a liquid ingredient or an alternative to dairy milk.",
        "flags": {"major_allergen"},
        "allergen": "tree nuts",
        "references": ["fda_allergens"],
    },
    {
        "key": "whey",
        "aliases": ["whey protein", "whey powder", "whey"],
        "category": "general_food_ingredient",
        "what_it_is": "A protein-rich ingredient derived from milk.",
        "purpose": "Used for protein, texture, or flavour.",
        "flags": {"dairy", "major_allergen"},
        "allergen": "milk",
        "references": ["fda_allergens"],
    },
    {
        "key": "casein",
        "aliases": ["casein", "caseinate", "sodium caseinate"],
        "category": "general_food_ingredient",
        "what_it_is": "A family of proteins found in milk.",
        "purpose": "Used for protein and functional texture properties.",
        "flags": {"dairy", "major_allergen"},
        "allergen": "milk",
        "references": ["fda_allergens"],
    },
    {
        "key": "egg",
        "aliases": ["egg white", "egg yolk", "egg albumen", "eggs", "egg"],
        "category": "general_food_ingredient",
        "what_it_is": "An egg-derived food ingredient.",
        "purpose": "Can contribute structure, binding, or texture.",
        "flags": {"egg", "major_allergen"},
        "allergen": "eggs",
        "references": ["fda_allergens"],
    },
    {
        "key": "soy",
        "aliases": ["soy protein", "soya protein", "soy flour", "soybean", "soybeans", "soy"],
        "category": "general_food_ingredient",
        "what_it_is": "A food ingredient derived from soybeans.",
        "purpose": "Can provide protein, flavour, or texture.",
        "flags": {"major_allergen"},
        "allergen": "soybeans",
        "references": ["fda_allergens"],
    },
    {
        "key": "wheat",
        "aliases": ["wheat flour", "whole wheat", "wheat starch", "wheat"],
        "category": "general_food_ingredient",
        "what_it_is": "A grain ingredient derived from wheat.",
        "purpose": "Flour and other wheat ingredients can provide structure and texture.",
        "flags": {"gluten", "major_allergen"},
        "allergen": "wheat",
        "references": ["fda_allergens"],
    },
    {
        "key": "barley",
        "aliases": ["barley malt", "barley flour", "barley"],
        "category": "general_food_ingredient",
        "what_it_is": "A cereal grain ingredient.",
        "purpose": "Used for flavour, malt, or grain structure.",
        "flags": {"gluten"},
        "references": [],
    },
    {
        "key": "rye",
        "aliases": ["rye flour", "rye"],
        "category": "general_food_ingredient",
        "what_it_is": "A cereal grain ingredient.",
        "purpose": "Used as a grain or flour ingredient.",
        "flags": {"gluten"},
        "references": [],
    },
    {
        "key": "peanut",
        "aliases": ["peanut butter", "peanut oil", "peanuts", "peanut"],
        "category": "general_food_ingredient",
        "what_it_is": "A food ingredient derived from peanuts.",
        "purpose": "Can provide flavour, protein, or texture.",
        "flags": {"major_allergen"},
        "allergen": "peanuts",
        "references": ["fda_allergens"],
    },
    {
        "key": "tree_nut",
        "aliases": [
            "almond", "almonds", "cashew", "cashews", "hazelnut", "hazelnuts",
            "pecan", "pecans", "pistachio", "pistachios", "walnut", "walnuts",
            "macadamia", "brazil nut", "tree nuts",
        ],
        "category": "general_food_ingredient",
        "what_it_is": "A tree-nut ingredient; the specific nut is identified by its name.",
        "purpose": "Can provide flavour, fat, or texture.",
        "flags": {"major_allergen"},
        "allergen": "tree nuts",
        "references": ["fda_allergens"],
    },
    {
        "key": "sesame",
        "aliases": ["sesame seeds", "sesame seed", "sesame oil", "sesame"],
        "category": "general_food_ingredient",
        "what_it_is": "A seed or oil ingredient derived from sesame.",
        "purpose": "Used for flavour, texture, or as an oil.",
        "flags": {"major_allergen"},
        "allergen": "sesame",
        "references": ["fda_allergens"],
    },
    {
        "key": "fish",
        "aliases": ["fish oil", "fish sauce", "anchovy", "anchovies", "salmon", "tuna", "fish"],
        "category": "general_food_ingredient",
        "what_it_is": "An ingredient derived from fish.",
        "purpose": "Can provide protein, flavour, or oil.",
        "flags": {"animal_meat", "major_allergen"},
        "allergen": "fish",
        "references": ["fda_allergens"],
    },
    {
        "key": "crustacean_shellfish",
        "aliases": ["shrimp", "prawn", "crab", "lobster", "crustacean shellfish"],
        "category": "general_food_ingredient",
        "what_it_is": "An ingredient derived from crustacean shellfish.",
        "purpose": "Used as a food ingredient for flavour or protein.",
        "flags": {"animal_meat", "major_allergen"},
        "allergen": "crustacean shellfish",
        "references": ["fda_allergens"],
    },
    {
        "key": "pork",
        "aliases": ["pork", "lard", "bacon", "ham"],
        "category": "general_food_ingredient",
        "what_it_is": "An ingredient derived from a pig.",
        "purpose": "Used as a meat, fat, or flavour ingredient.",
        "flags": {"animal_meat", "animal_derived", "pork"},
        "references": [],
    },
    {
        "key": "meat",
        "aliases": ["beef", "chicken", "poultry", "meat extract", "meat"],
        "category": "general_food_ingredient",
        "what_it_is": "A meat or poultry ingredient.",
        "purpose": "Used for protein, flavour, or texture.",
        "flags": {"animal_meat", "animal_derived", "source_uncertain"},
        "references": [],
    },
    {
        "key": "honey_bee_products",
        "aliases": ["beeswax", "shellac", "confectioner's glaze", "confectioners glaze"],
        "category": "other_additive",
        "what_it_is": "A glazing ingredient that may be derived from bee or insect products.",
        "purpose": "Used to coat foods and create a shiny surface.",
        "flags": {"animal_derived"},
        "references": [],
    },
]

CATEGORY_LABELS = {
    "general_food_ingredient": "General food ingredient",
    "preservative": "Preservative",
    "sweetener": "Sweetener",
    "colouring_agent": "Colouring agent",
    "emulsifier": "Emulsifier",
    "stabilizer": "Stabilizer or thickener",
    "other_additive": "Other additive",
    "unclassified": "Insufficient information",
}


def _normalize(value):
    normalized = str(value).casefold().replace("&", " and ")
    normalized = re.sub(r"\be\s+(\d{3,4})\b", r"e\1", normalized)
    return re.sub(r"[^a-z0-9]+", " ", normalized).strip()


_ALIASES = sorted(
    (
        (_normalize(alias), record)
        for record in _KNOWLEDGE
        for alias in record["aliases"]
    ),
    key=lambda item: len(item[0]),
    reverse=True,
)


def split_ingredients(ingredient_text):
    if not isinstance(ingredient_text, str):
        raise ValueError("Ingredients must be text.")
    if len(ingredient_text) > 10000:
        raise ValueError("Ingredient list must be at most 10000 characters.")
    if not ingredient_text.strip():
        raise ValueError("Enter an ingredient list to analyze.")

    def split_level(text):
        top_level = []
        current = []
        depth = 0
        for character in text:
            if character in "([":
                depth += 1
            elif character in ")]" and depth:
                depth -= 1
            if character in ",;" and depth == 0:
                top_level.append("".join(current).strip())
                current = []
            else:
                current.append(character)
        top_level.append("".join(current).strip())
        return top_level

    def flatten_component(component, nesting=0):
        if nesting > 20:
            raise ValueError("Ingredient sub-lists may be nested no more than 20 levels.")
        opening = next(
            (index for index, character in enumerate(component) if character in "(["),
            None,
        )
        if opening is None:
            return [component.strip(" \t\r\n.;•")]
        opener = component[opening]
        closer = ")" if opener == "(" else "]"
        depth = 1
        closing = None
        for index in range(opening + 1, len(component)):
            if component[index] == opener:
                depth += 1
            elif component[index] == closer:
                depth -= 1
                if depth == 0:
                    closing = index
                    break
        if closing is None:
            return [component.strip(" \t\r\n.;•")]
        main = component[:opening].strip(" \t\r\n.;•")
        nested = component[opening + 1:closing]
        after = component[closing + 1:].strip(" \t\r\n.;•")
        flattened = [main] if main else []
        for child in split_level(nested):
            flattened.extend(flatten_component(child, nesting + 1))
        if after:
            flattened.append(after)
        return flattened

    components = split_level(ingredient_text)
    ingredients = []
    for component in components:
        ingredients.extend(flatten_component(component))
    ingredients = [item for item in ingredients if item]
    if not ingredients:
        raise ValueError("No ingredients could be separated from this text.")
    if len(ingredients) > 100:
        raise ValueError("Ingredient list must contain no more than 100 items.")
    return ingredients


def _match_knowledge(name):
    normalized = _normalize(name)
    has_qualifier = re.search(
        r"\b(?:plant based|vegan|vegetarian|flavor|flavour)\b",
        normalized,
    )
    if has_qualifier:
        for alias, record in _ALIASES:
            if not record["flags"].intersection({"animal_derived", "animal_meat"}):
                continue
            if re.search(rf"(?:^| ){re.escape(alias)}(?: |$)", normalized):
                return None
    for alias, record in _ALIASES:
        if re.search(rf"(?:^| ){re.escape(alias)}(?: |$)", normalized):
            return record
    return None


def _dietary_considerations(record, preferences, presence):
    flags = record["flags"]
    results = []
    if presence == "possible":
        results.append(
            {
                "preference": "all",
                "status": "verify",
                "message": (
                    "This is listed as a possible trace or cross-contact warning, "
                    "not as a confirmed ingredient. Check the package and manufacturer."
                ),
            }
        )
    for preference in preferences:
        conflict = None
        status = "conflict"
        if preference == "vegan" and (
            "animal_derived" in flags or "dairy" in flags or "egg" in flags
        ):
            conflict = "This ingredient is animal-derived or comes from an animal food."
        elif preference == "vegetarian" and (
            "animal_meat" in flags or record["key"] in {"gelatin", "carmine"}
        ):
            conflict = "This ingredient may not fit a vegetarian diet."
        elif preference == "pescatarian" and (
            "animal_meat" in flags or record["key"] == "gelatin"
        ):
            conflict = "This ingredient may not fit a pescatarian diet."
        elif preference == "dairy_free" and "dairy" in flags:
            conflict = "This ingredient is derived from milk."
        elif preference == "gluten_free" and "gluten" in flags:
            conflict = "This ingredient is a gluten-containing grain."
        elif preference in {"halal", "kosher"} and "pork" in flags:
            conflict = "Pork is not compatible with this stated dietary preference."
        elif preference in {"halal", "kosher"} and "source_uncertain" in flags:
            status = "verify"
            conflict = (
                "The ingredient name does not identify its source or processing; "
                "check the package certification or manufacturer."
            )
        if conflict:
            if presence == "possible":
                status = "verify"
                conflict = f"Possible trace: {conflict[0].lower() + conflict[1:]}"
            results.append(
                {
                    "preference": preference,
                    "status": status,
                    "message": conflict,
                }
            )
    return results


def analyze_ingredient_list(ingredient_text, health_profile=None):
    names = split_ingredients(ingredient_text)
    profile = health_profile
    preferences = [
        preference
        for preference in (profile.dietary_preferences or [])
        if isinstance(preference, str) and preference != "none"
    ] if profile else []
    entries = []

    for name in names:
        possible = bool(re.match(r"^\s*(?:may contain|traces of|made in a facility)", name, re.I))
        record = _match_knowledge(name)
        if record is None:
            entries.append(
                {
                    "name": name,
                    "category": "unclassified",
                    "category_label": CATEGORY_LABELS["unclassified"],
                    "what_it_is": (
                        "This ingredient is not in the reviewed reference set."
                    ),
                    "common_purpose": (
                        "Its identity and purpose cannot be reliably determined from this match."
                    ),
                    "evidence_status": "insufficient_information",
                    "evidence_label": "Insufficient information",
                    "health_considerations": (
                        "No ingredient-specific health information is provided because "
                        "a reliable match was not available."
                    ),
                    "dietary_considerations": [],
                    "references": [],
                }
            )
            continue

        references = [REFERENCES[key] for key in record.get("references", [])]
        health_considerations = record.get("health_considerations")
        if record.get("allergen"):
            allergen = record["allergen"]
            health_considerations = (
                f"The FDA identifies {allergen} as a U.S. major food allergen. "
                "This is a label/reference note, not an assessment of an individual's allergy."
            )
        if not health_considerations:
            health_considerations = (
                "No ingredient-specific health effect is assessed by this reference set. "
                "This does not establish that no effects are possible."
            )
        entries.append(
            {
                "name": name,
                "category": record["category"],
                "category_label": CATEGORY_LABELS[record["category"]],
                "what_it_is": record["what_it_is"],
                "common_purpose": record["purpose"],
                "evidence_status": (
                    "reference_supported"
                    if record.get("allergen") or record.get("health_considerations")
                    else "purpose_reference_only"
                ),
                "evidence_label": (
                    "Health consideration has a cited reference"
                    if record.get("allergen") or record.get("health_considerations")
                    else "Identity and common use matched; health effects not assessed"
                ),
                "health_considerations": health_considerations,
                "dietary_considerations": _dietary_considerations(
                    record, preferences, "possible" if possible else "listed"
                ),
                "references": references,
            }
        )

    goal = profile.health_goal if profile else None
    goal_label = {
        "general_wellness": "general wellness",
        "maintain_weight": "maintaining weight",
        "lose_weight": "weight loss",
        "gain_weight": "weight gain",
        "build_muscle": "muscle building",
        "manage_condition": "condition management",
    }.get(goal)
    if goal_label == "condition management":
        goal_context = (
            "Your profile notes a condition-management goal. This ingredient list cannot "
            "assess condition-specific safety, treatment, or medical suitability."
        )
    elif goal_label:
        goal_context = (
            f"Your goal of {goal_label} is shown for context only. Ingredient names alone "
            "cannot determine whether this product supports that goal."
        )
    else:
        goal_context = (
            "No health goal is available in your profile; this analysis does not infer one."
        )

    conflict_count = sum(
        item["status"] == "conflict"
        for entry in entries
        for item in entry["dietary_considerations"]
    )
    verify_count = sum(
        item["status"] == "verify"
        for entry in entries
        for item in entry["dietary_considerations"]
    )
    unknown_count = sum(
        entry["evidence_status"] == "insufficient_information"
        for entry in entries
    )
    return {
        "method": "Local ingredient-name matching against a limited reviewed reference set",
        "entries": entries,
        "summary": {
            "ingredient_count": len(entries),
            "unmatched_count": unknown_count,
            "dietary_conflict_count": conflict_count,
            "dietary_verification_count": verify_count,
            "dietary_preferences": preferences,
            "health_goal_context": goal_context,
        },
        "disclaimer": (
            "Informational only, not medical advice. Ingredient matching may miss synonyms, "
            "complex sub-ingredients, allergens, or manufacturing cross-contact. Always check "
            "the package and consult a qualified professional for medical or allergy questions."
        ),
    }
