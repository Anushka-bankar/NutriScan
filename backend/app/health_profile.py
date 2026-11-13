from decimal import Decimal, InvalidOperation

from flask import Blueprint, current_app, g, jsonify, request
from sqlalchemy.exc import SQLAlchemyError

from app.auth import token_required
from app.extensions import db
from app.models import HealthProfile

health_profile_bp = Blueprint("health_profile", __name__)

ACTIVITY_FACTORS = {
    "sedentary": 1.2,
    "light": 1.375,
    "moderate": 1.55,
    "active": 1.725,
    "very_active": 1.9,
}
GENDERS = {"woman", "man", "non_binary", "prefer_not_to_say"}
DIETARY_PREFERENCES = {
    "vegetarian",
    "vegan",
    "pescatarian",
    "gluten_free",
    "dairy_free",
    "halal",
    "kosher",
    "none",
}
HEALTH_GOALS = {
    "general_wellness",
    "maintain_weight",
    "lose_weight",
    "gain_weight",
    "build_muscle",
    "manage_condition",
}


def calculate_bmi(weight_kg, height_cm, age):
    weight = float(weight_kg)
    height_m = float(height_cm) / 100
    bmi = round(weight / (height_m * height_m), 1)

    if age < 18:
        category = "not_classified"
        label = "Adult categories do not apply"
    elif bmi < 18.5:
        category, label = "underweight", "Below healthy range"
    elif bmi < 25:
        category, label = "healthy", "Healthy range"
    elif bmi < 30:
        category, label = "overweight", "Above healthy range"
    else:
        category, label = "obesity", "Obesity range"

    return {"value": bmi, "category": category, "label": label}


def estimate_daily_calories(age, height_cm, weight_kg, activity_level):
    if age < 18:
        return None

    weight = float(weight_kg)
    height = float(height_cm)
    activity = ACTIVITY_FACTORS[activity_level]
    female_bmr = 10 * weight + 6.25 * height - 5 * age - 161
    male_bmr = 10 * weight + 6.25 * height - 5 * age + 5
    return {
        "minimum": round(min(female_bmr, male_bmr) * activity),
        "maximum": round(max(female_bmr, male_bmr) * activity),
        "label": "Estimated daily maintenance range",
        "method": "Mifflin-St Jeor estimate; range reflects formula variation",
    }


def serialize_profile(profile):
    if profile is None:
        return None

    complete = all(
        value is not None
        for value in (
            profile.age,
            profile.height_cm,
            profile.weight_kg,
            profile.activity_level,
        )
    )
    bmi = (
        calculate_bmi(profile.weight_kg, profile.height_cm, profile.age)
        if complete
        else None
    )
    calories = (
        estimate_daily_calories(
            profile.age, profile.height_cm, profile.weight_kg, profile.activity_level
        )
        if complete
        else None
    )
    return {
        "age": profile.age,
        "gender": profile.gender,
        "height_cm": float(profile.height_cm) if profile.height_cm is not None else None,
        "weight_kg": float(profile.weight_kg) if profile.weight_kg is not None else None,
        "activity_level": profile.activity_level,
        "dietary_preferences": profile.dietary_preferences or [],
        "health_goal": profile.health_goal,
        "bmi": bmi,
        "daily_calories": calories,
        "created_at": profile.created_at.isoformat() if profile.created_at else None,
        "updated_at": profile.updated_at.isoformat() if profile.updated_at else None,
    }


def validate_profile(body):
    required = ("age", "height_cm", "weight_kg", "activity_level", "health_goal")
    missing = [field for field in required if field not in body or body[field] is None]
    if missing:
        return None, f"Required fields are missing: {', '.join(missing)}."

    try:
        age = int(body["age"])
        if isinstance(body["age"], bool) or age != float(body["age"]):
            raise ValueError
    except (TypeError, ValueError, OverflowError):
        return None, "Age must be a whole number between 1 and 120."
    if not 1 <= age <= 120:
        return None, "Age must be a whole number between 1 and 120."

    try:
        height_cm = Decimal(str(body["height_cm"]))
        weight_kg = Decimal(str(body["weight_kg"]))
    except (InvalidOperation, TypeError, ValueError):
        return None, "Height and weight must be valid numbers."
    if not height_cm.is_finite() or not Decimal("80") <= height_cm <= Decimal("250"):
        return None, "Height must be between 80 and 250 cm."
    if not weight_kg.is_finite() or not Decimal("20") <= weight_kg <= Decimal("400"):
        return None, "Weight must be between 20 and 400 kg."

    activity_level = body["activity_level"]
    if not isinstance(activity_level, str) or activity_level not in ACTIVITY_FACTORS:
        return None, "Choose a valid activity level."
    health_goal = body["health_goal"]
    if not isinstance(health_goal, str) or health_goal not in HEALTH_GOALS:
        return None, "Choose a valid health goal."

    gender = body.get("gender") or None
    if gender is not None and (
        not isinstance(gender, str) or gender not in GENDERS
    ):
        return None, "Choose a valid gender option."

    preferences = body.get("dietary_preferences", [])
    if (
        not isinstance(preferences, list)
        or len(preferences) > len(DIETARY_PREFERENCES)
        or any(
            not isinstance(item, str) or item not in DIETARY_PREFERENCES
            for item in preferences
        )
    ):
        return None, "Choose valid dietary preferences."

    return {
        "age": age,
        "gender": gender,
        "height_cm": height_cm,
        "weight_kg": weight_kg,
        "activity_level": activity_level,
        "dietary_preferences": sorted(set(preferences)),
        "health_goal": health_goal,
    }, None


def _body():
    if not request.is_json:
        return None
    value = request.get_json(silent=True)
    return value if isinstance(value, dict) else None


@health_profile_bp.get("")
@token_required
def get_health_profile():
    profile = db.session.get(HealthProfile, g.current_user.id)
    return jsonify({"profile": serialize_profile(profile)})


@health_profile_bp.put("")
@token_required
def save_health_profile():
    body = _body()
    if body is None:
        return jsonify({"message": "A JSON request body is required."}), 400

    values, error = validate_profile(body)
    if error:
        return jsonify({"message": error}), 400

    try:
        profile = db.session.get(HealthProfile, g.current_user.id)
        if profile is None:
            profile = HealthProfile(user_id=g.current_user.id)
            db.session.add(profile)

        for field, value in values.items():
            setattr(profile, field, value)
        db.session.commit()
        return jsonify({"profile": serialize_profile(profile)}), 200
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception("Could not save health profile.")
        return jsonify({"message": "Could not save your profile. Please try again."}), 500
