from flask import Blueprint, current_app, g, jsonify, request
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.auth import token_required
from app.claim_analyzer import analyze_food_claims
from app.extensions import db
from app.models import HealthProfile, Product, ProductFoodClaimAnalysis

food_claims_bp = Blueprint("food_claims", __name__)
MAX_CLAIM_TEXT = 20000

_NUTRIENTS = (
    "energy_kj",
    "calories_kcal",
    "carbohydrates_g",
    "sugars_g",
    "protein_g",
    "total_fat_g",
    "saturated_fat_g",
    "fibre_g",
    "sodium_mg",
)


def _owned_product(product_id):
    return db.session.execute(
        select(Product).where(
            Product.id == product_id,
            Product.created_by == g.current_user.id,
        )
    ).scalar_one_or_none()


def _product_snapshot(product):
    return {
        "id": product.id,
        "name": product.name,
        "brand": product.brand,
        "category": product.category,
        "serving_size_g": (
            float(product.serving_size_g)
            if product.serving_size_g is not None
            else None
        ),
        "ingredients": product.ingredients,
        "nutrition_per_100g": {
            field: (
                float(getattr(product, field))
                if getattr(product, field) is not None
                else None
            )
            for field in _NUTRIENTS
        },
        "source_type": product.source_type,
        "source_label": product.source_label,
    }


def _analysis_json(entry):
    return {
        "id": entry.id,
        "product_id": entry.product_id,
        "product_identity_snapshot": entry.product_identity_snapshot,
        "product_name": entry.product_name_snapshot,
        "claim_text": entry.claim_text,
        "input_source": entry.input_source,
        "product_snapshot": entry.product_snapshot,
        "analyzed_at": entry.analyzed_at.isoformat() if entry.analyzed_at else None,
        **entry.analysis_result,
    }


@food_claims_bp.get("/claims/history")
@token_required
def get_food_claim_history():
    product_id = request.args.get("product_id")
    if product_id is not None:
        try:
            product_id = int(product_id)
        except (TypeError, ValueError):
            return jsonify({"message": "product_id must be a positive integer."}), 400
        if product_id < 1:
            return jsonify({"message": "product_id must be a positive integer."}), 400

    try:
        query = select(ProductFoodClaimAnalysis).where(
            ProductFoodClaimAnalysis.user_id == g.current_user.id
        )
        if product_id is not None:
            query = query.where(
                ProductFoodClaimAnalysis.product_identity_snapshot == product_id
            )
        entries = db.session.execute(
            query.order_by(
                ProductFoodClaimAnalysis.analyzed_at.desc(),
                ProductFoodClaimAnalysis.id.desc(),
            ).limit(100)
        ).scalars().all()
        return jsonify({"history": [_analysis_json(entry) for entry in entries]})
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception("Could not load food claim history.")
        return jsonify(
            {"message": "Could not load claim analysis history. Please try again."}
        ), 500


@food_claims_bp.post("/<int:product_id>/claims/analyze")
@token_required
def create_food_claim_analysis(product_id):
    if not request.is_json:
        return jsonify({"message": "A JSON request body is required."}), 400
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return jsonify({"message": "A JSON object is required."}), 400

    try:
        product = _owned_product(product_id)
        if product is None:
            return jsonify({"message": "Product not found."}), 404

        supplied_text = body.get("claim_text")
        if supplied_text is None:
            claim_text = product.packaging_text or ""
        else:
            claim_text = supplied_text
        if not isinstance(claim_text, str):
            return jsonify({"message": "Claim text must be text."}), 400
        if not claim_text.strip():
            return jsonify(
                {"message": "Enter packaging claims or save OCR-extracted package text first."}
            ), 400
        if len(claim_text) > MAX_CLAIM_TEXT:
            return jsonify(
                {"message": f"Claim text must be at most {MAX_CLAIM_TEXT} characters."}
            ), 400

        input_source = (
            "ocr"
            if product.packaging_text
            and claim_text.strip() == product.packaging_text.strip()
            else "manual_or_edited"
        )
        profile = db.session.get(HealthProfile, g.current_user.id)
        result = analyze_food_claims(
            claim_text,
            product,
            dietary_preferences=(
                profile.dietary_preferences if profile is not None else []
            ),
            manual_input=input_source != "ocr",
        )
        snapshot = _product_snapshot(product)
        entry = ProductFoodClaimAnalysis(
            user_id=g.current_user.id,
            product_id=product.id,
            product_identity_snapshot=product.id,
            product_name_snapshot=product.name,
            claim_text=claim_text.strip(),
            input_source=input_source,
            product_snapshot=snapshot,
            analysis_result=result,
        )
        db.session.add(entry)
        db.session.commit()
        return jsonify({"analysis": _analysis_json(entry)}), 201
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception("Could not save food claim analysis.")
        return jsonify(
            {"message": "Could not save claim analysis. Please try again."}
        ), 500
