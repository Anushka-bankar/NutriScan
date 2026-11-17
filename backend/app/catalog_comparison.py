import re
from decimal import Decimal

from flask import Blueprint, current_app, jsonify, request
from sqlalchemy import func, or_, select
from sqlalchemy.exc import SQLAlchemyError

from app.auth import token_required
from app.catalog import NUTRITION_FIELDS, catalog_product_json
from app.extensions import db
from app.models import PackagedFoodCatalog

catalog_comparison_bp = Blueprint("catalog_comparison", __name__)

POSITIVE_INTEGER = re.compile(r"^[0-9]+$")
MAX_ALTERNATIVE_LIMIT = 20
DEFAULT_ALTERNATIVE_LIMIT = 5

NUTRIENT_UNITS = {
    "calories_kcal": "kcal",
    "carbohydrates_g": "g",
    "protein_g": "g",
    "total_fat_g": "g",
    "saturated_fat_g": "g",
    "trans_fat_g": "g",
    "sugar_g": "g",
    "sodium_mg": "mg",
    "dietary_fiber_g": "g",
    "cholesterol_mg": "mg",
    "calcium_mg": "mg",
    "iron_mg": "mg",
}

ALTERNATIVE_NUTRIENTS = (
    ("calories_kcal", "Calories", "kcal", "lower"),
    ("sugar_g", "Sugar", "g", "lower"),
    ("saturated_fat_g", "Saturated fat", "g", "lower"),
    ("sodium_mg", "Sodium", "mg", "lower"),
    ("protein_g", "Protein", "g", "higher"),
    ("dietary_fiber_g", "Dietary fiber", "g", "higher"),
)


def _query_error(allowed_parameters):
    unknown = sorted(set(request.args.keys()) - allowed_parameters)
    if unknown:
        return f"Unsupported query parameter: {unknown[0]}."
    for parameter in request.args.keys():
        if len(request.args.getlist(parameter)) != 1:
            return f"Query parameter '{parameter}' may only be provided once."
    return None


def _product_ids():
    if error := _query_error({"product_id_1", "product_id_2"}):
        return None, error
    result = []
    for parameter in ("product_id_1", "product_id_2"):
        raw_value = request.args.get(parameter)
        if raw_value is None:
            return None, f"{parameter} is required."
        if len(raw_value) > 10 or not POSITIVE_INTEGER.fullmatch(raw_value):
            return None, f"{parameter} must be a positive integer."
        value = int(raw_value)
        if value < 1:
            return None, f"{parameter} must be a positive integer."
        result.append(value)
    if result[0] == result[1]:
        return None, "Choose two different catalog products."
    return result, None


def _normalized_category(value):
    return value.strip().casefold() if isinstance(value, str) and value.strip() else None


def _per_100g_value(product, model_field):
    value = getattr(product, model_field)
    if value is None:
        return None
    if product.nutrition_basis == "per_100g":
        return value
    if product.nutrition_basis != "per_serving_inferred":
        return None
    if product.serving_size_g is None or product.serving_size_g <= 0:
        return None
    return value * Decimal("100") / product.serving_size_g


def _can_normalize_per_100g(product):
    if product.nutrition_basis == "per_100g":
        return True
    return (
        product.nutrition_basis == "per_serving_inferred"
        and product.serving_size_g is not None
        and product.serving_size_g > 0
    )


def _per_100g_basis(product):
    if product.nutrition_basis == "per_100g":
        return "source_per_100g"
    if _can_normalize_per_100g(product):
        return "derived_from_inferred_per_serving"
    return "unavailable"


def _json_number(value):
    if value is None:
        return None
    return round(float(value), 6)


def _comparison_product_json(product):
    result = catalog_product_json(product, include_raw_values=True)
    result["nutrition_per_100g_comparison"] = {
        public_name: _json_number(_per_100g_value(product, model_field))
        for public_name, model_field in NUTRITION_FIELDS.items()
    }
    result["nutrition_per_100g_comparison_basis"] = _per_100g_basis(product)
    return result


def _serving_size_relation(product_1, product_2):
    if product_1.serving_size_g is None or product_2.serving_size_g is None:
        return "unavailable"
    if product_1.serving_size_g == product_2.serving_size_g:
        return "same"
    return "different"


def _comparison_json(product_1, product_2):
    basis_matches = product_1.nutrition_basis == product_2.nutrition_basis
    serving_relation = _serving_size_relation(product_1, product_2)
    per_serving_comparable = (
        product_1.nutrition_basis == "per_serving_inferred"
        and product_2.nutrition_basis == "per_serving_inferred"
        and serving_relation == "same"
    )
    normalized_comparable = all(
        _can_normalize_per_100g(product) for product in (product_1, product_2)
    )

    nutrients = {}
    for public_name, model_field in NUTRITION_FIELDS.items():
        value_1 = getattr(product_1, model_field)
        value_2 = getattr(product_2, model_field)
        per_100g_1 = _per_100g_value(product_1, model_field)
        per_100g_2 = _per_100g_value(product_2, model_field)
        can_compare_per_100g = per_100g_1 is not None and per_100g_2 is not None
        difference = per_100g_2 - per_100g_1 if can_compare_per_100g else None
        nutrients[public_name] = {
            "unit": NUTRIENT_UNITS[public_name],
            "product_1_per_serving": _json_number(value_1),
            "product_2_per_serving": _json_number(value_2),
            "per_serving_comparable": (
                per_serving_comparable and value_1 is not None and value_2 is not None
            ),
            "product_1_per_100g_comparable": _json_number(per_100g_1),
            "product_2_per_100g_comparable": _json_number(per_100g_2),
            "difference_per_100g_product_2_minus_product_1": _json_number(difference),
            "per_100g_comparable": can_compare_per_100g,
        }

    notes = []
    if serving_relation == "different":
        notes.append(
            "Serving sizes differ; per-serving amounts are not directly comparable."
        )
    elif serving_relation == "unavailable":
        notes.append(
            "One or both serving sizes are unavailable; per-serving equivalence cannot be confirmed."
        )
    if not basis_matches:
        notes.append(
            "Measurement bases differ; compare only values normalized to a supported common basis."
        )
    if normalized_comparable:
        notes.append(
            "Per-100 g values are normalized only from supported stored bases; inferred serving values remain source data, not verified label facts."
        )
    else:
        notes.append(
            "Per-100 g comparison is unavailable where serving size or measurement basis is unsupported."
        )
    return {
        "measurement_bases_match": basis_matches,
        "serving_size_relation": serving_relation,
        "per_serving_values_comparable": per_serving_comparable,
        "per_100g_normalization_possible": normalized_comparable,
        "nutrients": nutrients,
        "notes": notes,
    }


def _category_match(selected, candidate):
    selected_category = _normalized_category(selected.category)
    candidate_category = _normalized_category(candidate.category)
    selected_subcategory = _normalized_category(selected.sub_category)
    candidate_subcategory = _normalized_category(candidate.sub_category)
    same_category = bool(
        selected_category and candidate_category == selected_category
    )
    same_subcategory = bool(
        selected_subcategory and candidate_subcategory == selected_subcategory
    )
    if same_category and same_subcategory:
        return 0, "same_category_and_subcategory", (
            "Same category and subcategory as the selected product."
        )
    if same_category:
        return 1, "same_category", "Same category as the selected product."
    if same_subcategory:
        return 2, "same_subcategory_across_categories", (
            "Shares a subcategory label with the selected product."
        )
    return None


def _alternative_evaluation(selected, candidate):
    changes = []
    improvements = []
    tradeoffs = []
    unavailable = []
    for public_name, label, unit, preferred in ALTERNATIVE_NUTRIENTS:
        model_field = NUTRITION_FIELDS[public_name]
        selected_value = _per_100g_value(selected, model_field)
        candidate_value = _per_100g_value(candidate, model_field)
        if selected_value is None or candidate_value is None:
            unavailable.append(label)
            continue

        difference = candidate_value - selected_value
        if difference == 0:
            direction = "same"
        elif difference < 0:
            direction = "lower"
        else:
            direction = "higher"
        change = {
            "nutrient": label,
            "unit": unit,
            "selected_value_per_100g_comparable": _json_number(selected_value),
            "alternative_value_per_100g_comparable": _json_number(candidate_value),
            "difference_alternative_minus_selected": _json_number(difference),
            "direction": direction,
        }
        changes.append(change)
        if direction == preferred:
            delta = abs(difference)
            message = (
                f"{label} is {_json_number(delta)} {unit} {direction} per 100 g."
            )
            improvements.append(message)
            change["interpretation"] = "favorable_difference"
        elif direction != "same":
            message = (
                f"{label} is {_json_number(abs(difference))} {unit} {direction} per 100 g."
            )
            tradeoffs.append(message)
            change["interpretation"] = "tradeoff"
        else:
            change["interpretation"] = "same"

    return {
        "changes": changes,
        "improvements": improvements,
        "tradeoffs": tradeoffs,
        "unavailable": unavailable,
    }


@catalog_comparison_bp.get("/products/compare")
@token_required
def compare_catalog_products():
    product_ids, error = _product_ids()
    if error:
        return jsonify({"message": error}), 400
    try:
        products = db.session.execute(
            select(PackagedFoodCatalog).where(
                PackagedFoodCatalog.id.in_(product_ids)
            )
        ).scalars().all()
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception("Could not compare catalog products.")
        return jsonify({"message": "Could not compare products. Please try again."}), 500

    products_by_id = {product.id: product for product in products}
    if any(product_id not in products_by_id for product_id in product_ids):
        return jsonify({"message": "One or both catalog products were not found."}), 404

    product_1, product_2 = (
        products_by_id[product_id] for product_id in product_ids
    )
    return jsonify(
        {
            "product_1": _comparison_product_json(product_1),
            "product_2": _comparison_product_json(product_2),
            "comparison": _comparison_json(product_1, product_2),
        }
    )


@catalog_comparison_bp.get("/products/<int:product_id>/alternatives")
@token_required
def recommend_catalog_alternatives(product_id):
    if error := _query_error({"limit"}):
        return jsonify({"message": error}), 400
    raw_limit = request.args.get("limit", str(DEFAULT_ALTERNATIVE_LIMIT))
    if len(raw_limit) > 2 or not POSITIVE_INTEGER.fullmatch(raw_limit):
        return jsonify(
            {"message": f"limit must be an integer between 1 and {MAX_ALTERNATIVE_LIMIT}."}
        ), 400
    limit = int(raw_limit)
    if not 1 <= limit <= MAX_ALTERNATIVE_LIMIT:
        return jsonify(
            {"message": f"limit must be an integer between 1 and {MAX_ALTERNATIVE_LIMIT}."}
        ), 400

    try:
        selected = db.session.execute(
            select(PackagedFoodCatalog).where(PackagedFoodCatalog.id == product_id)
        ).scalar_one_or_none()
        if selected is None:
            return jsonify({"message": "Catalog product not found."}), 404

        conditions = []
        if _normalized_category(selected.category):
            conditions.append(
                func.upper(func.trim(PackagedFoodCatalog.category))
                == selected.category.strip().upper()
            )
        if _normalized_category(selected.sub_category):
            conditions.append(
                func.upper(func.trim(PackagedFoodCatalog.sub_category))
                == selected.sub_category.strip().upper()
            )
        candidates = []
        if conditions:
            candidates = db.session.execute(
                select(PackagedFoodCatalog)
                .where(
                    PackagedFoodCatalog.id != selected.id,
                    or_(*conditions),
                )
            ).scalars().all()
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception("Could not find catalog alternatives.")
        return jsonify(
            {"message": "Could not load product alternatives. Please try again."}
        ), 500

    evaluated = []
    for candidate in candidates:
        match = _category_match(selected, candidate)
        if match is None:
            continue
        category_rank, category_match, category_reason = match
        evaluation = _alternative_evaluation(selected, candidate)
        if len(evaluation["changes"]) < 2 or not evaluation["improvements"]:
            continue
        reasons = [category_reason, *evaluation["improvements"]]
        if evaluation["tradeoffs"]:
            reasons.extend(
                f"Trade-off: {tradeoff}" for tradeoff in evaluation["tradeoffs"]
            )
        if evaluation["unavailable"]:
            reasons.append(
                "Not compared because data was unavailable for: "
                + ", ".join(evaluation["unavailable"])
                + "."
            )
        evaluated.append(
            {
                "_rank": (
                    category_rank,
                    -len(evaluation["improvements"]),
                    len(evaluation["tradeoffs"]),
                    -len(evaluation["changes"]),
                    candidate.product_name.casefold(),
                    candidate.id,
                ),
                "product": catalog_product_json(candidate),
                "category_match": category_match,
                "nutrient_changes": evaluation["changes"],
                "why_suggested": reasons,
                "data_note": (
                    "Measured differences use comparable per-100 g values from a "
                    "supported stored basis. Missing values were not inferred."
                ),
            }
        )
    evaluated.sort(key=lambda result: result["_rank"])
    recommendations = []
    for result in evaluated[:limit]:
        result.pop("_rank")
        recommendations.append(result)

    if not conditions:
        message = (
            "Category information is unavailable; similar alternatives could not be identified."
        )
    elif recommendations:
        message = (
            "Alternatives have at least two comparable nutrition values and at least "
            "one measured favorable difference. This is not an overall health rating."
        )
    else:
        message = (
            "No categorized alternative met the minimum comparison rules with the "
            "available data."
        )
    return jsonify(
        {
            "selected_product": catalog_product_json(selected),
            "recommendations": recommendations,
            "recommendations_found": len(recommendations),
            "message": message,
            "logic": {
                "category_matching": (
                    "Same category/subcategory is prioritized, followed by same "
                    "category and then a matching subcategory label."
                ),
                "eligibility": (
                    "At least two comparable nutrients and one favorable pairwise "
                    "difference are required."
                ),
                "nutrients_considered": [
                    item[1] for item in ALTERNATIVE_NUTRIENTS
                ],
                "preferred_directions": {
                    "calories": "lower",
                    "sugar": "lower",
                    "saturated_fat": "lower",
                    "sodium": "lower",
                    "protein": "higher",
                    "dietary_fiber": "higher",
                },
                "ranking": (
                    "Category match, then number of favorable differences, fewer "
                    "trade-offs, more comparable values, and product name. No score is calculated."
                ),
                "disclaimer": (
                    "These are transparent nutrient comparisons, not medical advice, "
                    "a universal health claim, or a validated nutrition rating."
                ),
            },
        }
    )
