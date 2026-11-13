from flask import Blueprint, current_app, g, jsonify
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.auth import token_required
from app.extensions import db
from app.models import HealthProfile, Product
from app.product_options import PRODUCT_CATEGORIES, PRODUCT_DIETARY_TAGS
from app.products import NUTRIENT_FIELDS, _product_json

recommendations_bp = Blueprint("recommendations", __name__)

COMPARISON_NUTRIENTS = tuple(NUTRIENT_FIELDS)
GOAL_RULES = {
    "lose_weight": {
        "primary": (("calories_kcal", "lower"),),
        "secondary": (
            ("sugars_g", "lower"),
            ("saturated_fat_g", "lower"),
            ("sodium_mg", "lower"),
            ("fibre_g", "higher"),
            ("protein_g", "higher"),
        ),
        "goal_label": "weight-loss goal",
    },
    "build_muscle": {
        "primary": (("protein_g", "higher"),),
        "secondary": (
            ("calories_kcal", "higher"),
            ("fibre_g", "higher"),
            ("sugars_g", "lower"),
            ("saturated_fat_g", "lower"),
            ("sodium_mg", "lower"),
        ),
        "goal_label": "muscle-building goal",
    },
    "gain_weight": {
        "primary": (("calories_kcal", "higher"),),
        "secondary": (
            ("protein_g", "higher"),
            ("fibre_g", "higher"),
            ("sugars_g", "lower"),
            ("saturated_fat_g", "lower"),
            ("sodium_mg", "lower"),
        ),
        "goal_label": "weight-gain goal",
    },
    "maintain_weight": {
        "primary": (
            ("sugars_g", "lower"),
            ("saturated_fat_g", "lower"),
            ("sodium_mg", "lower"),
        ),
        "secondary": (
            ("calories_kcal", "lower"),
            ("fibre_g", "higher"),
            ("protein_g", "higher"),
        ),
        "goal_label": "weight-maintenance goal",
    },
    "general_wellness": {
        "primary": (
            ("sugars_g", "lower"),
            ("saturated_fat_g", "lower"),
            ("sodium_mg", "lower"),
        ),
        "secondary": (
            ("calories_kcal", "lower"),
            ("fibre_g", "higher"),
            ("protein_g", "higher"),
        ),
        "goal_label": "general-wellness goal",
    },
}


def _dietary_requirements(profile):
    preferences = profile.dietary_preferences or []
    return {
        preference
        for preference in preferences
        if preference in PRODUCT_DIETARY_TAGS
    }


def _value(product, field):
    value = getattr(product, field)
    return float(value) if value is not None else None


def _is_better(candidate_value, target_value, direction):
    if candidate_value is None or target_value is None:
        return False
    if direction == "lower":
        return candidate_value < target_value
    return candidate_value > target_value


def _metric_differences(target, candidate, goal):
    rules = GOAL_RULES[goal]
    directions = dict((*rules["primary"], *rules["secondary"]))
    differences = []
    for field in COMPARISON_NUTRIENTS:
        target_value = _value(target, field)
        candidate_value = _value(candidate, field)
        direction = directions.get(field)
        improved = (
            direction is not None
            and _is_better(candidate_value, target_value, direction)
        )
        differences.append(
            {
                "field": field,
                "label": NUTRIENT_FIELDS[field][0],
                "unit": "mg" if field == "sodium_mg" else (
                    "kJ" if field == "energy_kj" else "kcal" if field == "calories_kcal" else "g"
                ),
                "target_value": target_value,
                "alternative_value": candidate_value,
                "difference": (
                    round(candidate_value - target_value, 2)
                    if candidate_value is not None and target_value is not None
                    else None
                ),
                "available": target_value is not None and candidate_value is not None,
                "goal_direction": direction,
                "goal_improvement": improved,
            }
        )
    return differences


def _recommendation_for(target, candidate, goal):
    rules = GOAL_RULES.get(goal)
    if rules is None:
        return None

    improved_primary = []
    for field, direction in rules["primary"]:
        base_value = _value(target, field)
        candidate_value = _value(candidate, field)
        if _is_better(candidate_value, base_value, direction):
            improved_primary.append((field, direction, base_value, candidate_value))
    if not improved_primary:
        return None

    improvements = list(improved_primary)
    tradeoffs = []
    for field, direction in rules["secondary"]:
        base_value = _value(target, field)
        candidate_value = _value(candidate, field)
        if base_value is None or candidate_value is None:
            continue
        if _is_better(candidate_value, base_value, direction):
            improvements.append((field, direction, base_value, candidate_value))
        elif candidate_value != base_value:
            tradeoffs.append((field, base_value, candidate_value))

    reasons = [
        f"{NUTRIENT_FIELDS[field][0]} per 100 g "
        f"{'decreases' if direction == 'lower' else 'increases'} "
        f"from {base:g} to {alternative:g} "
        f"{'mg' if field == 'sodium_mg' else 'kcal' if field == 'calories_kcal' else 'g'}."
        for field, direction, base, alternative in improvements
    ]
    if tradeoffs:
        reasons.append(
            "Consider these measured trade-offs: "
            + "; ".join(
                f"{NUTRIENT_FIELDS[field][0].lower()} "
                f"{'increases' if alternative > base else 'decreases'} "
                f"from {base:g} to {alternative:g} "
                f"{'mg' if field == 'sodium_mg' else 'kcal' if field == 'calories_kcal' else 'g'}"
                for field, base, alternative in tradeoffs
            )
            + "."
        )

    return {
        "product": _product_json(candidate),
        "goal_label": rules["goal_label"],
        "reasons": reasons,
        "primary_improvements": len(improved_primary),
        "tradeoffs_count": len(tradeoffs),
        "comparisons": _metric_differences(target, candidate, goal),
    }


def recommend_alternatives(target, candidates, profile):
    category = target.category
    if not category or category == "other":
        return [], "Add a specific food category to this product to find comparable alternatives."

    goal = profile.health_goal
    if profile.age is not None and profile.age < 18:
        return [], (
            "Personalized product recommendations are not provided for users under 18. "
            "A pediatric healthcare professional can help interpret nutrition needs."
        )
    if goal == "manage_condition":
        return [], (
            "A specific health condition was not provided. NutriScan does not make "
            "condition-specific product recommendations."
        )
    if goal not in GOAL_RULES:
        return [], "Choose a supported health goal in your profile to personalize recommendations."

    requirements = _dietary_requirements(profile)
    alternatives = []
    for candidate in candidates:
        if candidate.id == target.id or candidate.category != category:
            continue
        candidate_tags = set(candidate.dietary_tags or [])
        if requirements and not requirements.issubset(candidate_tags):
            continue
        recommendation = _recommendation_for(target, candidate, goal)
        if recommendation is not None:
            alternatives.append(recommendation)

    def sort_key(recommendation):
        product = recommendation["product"]
        return (
            -recommendation["primary_improvements"],
            recommendation["tradeoffs_count"],
            product["name"].casefold(),
            product["id"],
        )

    alternatives.sort(key=sort_key)
    if not alternatives:
        return [], (
            "No suitable alternative was found in your saved products for this category "
            "and health goal. Recommendations also require matching dietary tags when "
            "your profile lists dietary preferences."
        )
    return alternatives[:10], None


@recommendations_bp.get("/<int:product_id>/recommendations")
@token_required
def product_recommendations(product_id):
    try:
        target = db.session.execute(
            select(Product).where(
                Product.id == product_id,
                Product.created_by == g.current_user.id,
            )
        ).scalar_one_or_none()
        if target is None:
            return jsonify({"message": "Product not found."}), 404

        profile = db.session.get(HealthProfile, g.current_user.id)
        if profile is None or not profile.health_goal:
            return jsonify(
                {"message": "Complete your health profile to get personalized recommendations."}
            ), 400

        candidates = db.session.execute(
            select(Product).where(Product.created_by == g.current_user.id)
        ).scalars().all()
        recommendations, message = recommend_alternatives(
            target, candidates, profile
        )
        return jsonify(
            {
                "target": _product_json(target),
                "health_goal": profile.health_goal,
                "recommendations": recommendations,
                "message": message,
                "rules": (
                    "Products must have the same explicit category. A recommendation "
                    "must improve a primary goal-specific nutrient. Results are ordered "
                    "by the number of primary improvements, then fewer measured trade-offs. "
                    "Comparisons use per-100 g values; missing values are unavailable. "
                    "Dietary tags must match every preference recorded in your profile."
                ),
            }
        )
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception("Could not retrieve product recommendations.")
        return jsonify({"message": "Could not load recommendations. Please try again."}), 500
