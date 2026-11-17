from flask import Blueprint, current_app, g, jsonify, request
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.auth import token_required
from app.extensions import db
from app.ingredient_comparison import compare_ingredient_snapshots
from app.ingredient_analyzer import analyze_ingredient_list
from app.models import HealthProfile, Product, ProductIngredientAnalysis

ingredient_analysis_bp = Blueprint("ingredient_analysis", __name__)


def _owned_product(product_id):
    return db.session.execute(
        select(Product).where(
            Product.id == product_id,
            Product.created_by == g.current_user.id,
        )
    ).scalar_one_or_none()


def _analysis_json(entry):
    return {
        "id": entry.id,
        "product_id": entry.product_id,
        "product_identity_snapshot": entry.product_identity_snapshot,
        "product_name": entry.product_name_snapshot,
        "ingredients_text": entry.ingredients_text,
        "analyzed_at": entry.analyzed_at.isoformat() if entry.analyzed_at else None,
        **entry.analysis_result,
    }


def _history_json(entry):
    return {
        "id": entry.id,
        "product_id": entry.product_id,
        "product_identity_snapshot": entry.product_identity_snapshot,
        "product_available": entry.product_id is not None,
        "product_name": entry.product_name_snapshot,
        "ingredients_text": entry.ingredients_text,
        "analyzed_at": entry.analyzed_at.isoformat() if entry.analyzed_at else None,
    }


@ingredient_analysis_bp.get("/ingredients/history")
@token_required
def get_ingredient_analysis_history():
    try:
        entries = db.session.execute(
            select(ProductIngredientAnalysis)
            .where(ProductIngredientAnalysis.user_id == g.current_user.id)
            .order_by(
                ProductIngredientAnalysis.analyzed_at.desc(),
                ProductIngredientAnalysis.id.desc(),
            )
        ).scalars().all()
        return jsonify({"history": [_history_json(entry) for entry in entries]})
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception("Could not load ingredient analysis history.")
        return jsonify({"message": "Could not load ingredient history. Please try again."}), 500


@ingredient_analysis_bp.post("/ingredients/compare")
@token_required
def compare_ingredient_analyses():
    if not request.is_json:
        return jsonify({"message": "A JSON request body is required."}), 400
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return jsonify({"message": "A JSON object is required."}), 400

    ids = []
    for field in ("older_analysis_id", "newer_analysis_id"):
        value = body.get(field)
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            return jsonify({"message": f"{field} must be a positive integer."}), 400
        ids.append(value)
    if ids[0] == ids[1]:
        return jsonify({"message": "Choose two different ingredient analyses."}), 400

    try:
        entries = db.session.execute(
            select(ProductIngredientAnalysis).where(
                ProductIngredientAnalysis.id.in_(ids),
                ProductIngredientAnalysis.user_id == g.current_user.id,
            )
        ).scalars().all()
        by_id = {entry.id: entry for entry in entries}
        if len(by_id) != 2:
            return jsonify({"message": "Ingredient analysis not found."}), 404

        older = by_id[ids[0]]
        newer = by_id[ids[1]]
        if (older.analyzed_at, older.id) >= (newer.analyzed_at, newer.id):
            return jsonify(
                {"message": "The older analysis must be earlier than the newer analysis."}
            ), 400
        if (
            older.product_identity_snapshot is None
            or newer.product_identity_snapshot is None
            or older.product_identity_snapshot != newer.product_identity_snapshot
        ):
            return jsonify(
                {"message": "Choose two analyses of the same product."}
            ), 400

        if (
            older.product_id is not None
            and older.product_id != older.product_identity_snapshot
        ) or (
            newer.product_id is not None
            and newer.product_id != newer.product_identity_snapshot
        ):
            current_app.logger.error(
                "Ingredient analysis product identity snapshot is inconsistent."
            )
            return jsonify({"message": "These analyses cannot be compared."}), 409

        comparison = compare_ingredient_snapshots(
            older.analysis_result, newer.analysis_result
        )
        return jsonify(
            {
                "older": _history_json(older),
                "newer": _history_json(newer),
                **comparison,
            }
        )
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception("Could not compare ingredient analyses.")
        return jsonify({"message": "Could not compare ingredient analyses. Please try again."}), 500


@ingredient_analysis_bp.get("/<int:product_id>/ingredients/latest")
@token_required
def get_latest_ingredient_analysis(product_id):
    try:
        product = _owned_product(product_id)
        if product is None:
            return jsonify({"message": "Product not found."}), 404
        entry = db.session.execute(
            select(ProductIngredientAnalysis)
            .where(
                ProductIngredientAnalysis.product_id == product.id,
                ProductIngredientAnalysis.user_id == g.current_user.id,
            )
            .order_by(
                ProductIngredientAnalysis.analyzed_at.desc(),
                ProductIngredientAnalysis.id.desc(),
            )
            .limit(1)
        ).scalar_one_or_none()
        return jsonify(
            {
                "analysis": _analysis_json(entry) if entry else None,
                "product_name": product.name,
                "ingredients_text": product.ingredients or "",
            }
        )
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception("Could not load ingredient analysis.")
        return jsonify({"message": "Could not load ingredient analysis. Please try again."}), 500


@ingredient_analysis_bp.post("/<int:product_id>/ingredients/analyze")
@token_required
def create_ingredient_analysis(product_id):
    if not request.is_json:
        return jsonify({"message": "A JSON request body is required."}), 400
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return jsonify({"message": "A JSON object is required."}), 400
    try:
        product = _owned_product(product_id)
        if product is None:
            return jsonify({"message": "Product not found."}), 404
        ingredients = (
            body.get("ingredients")
            if "ingredients" in body
            else product.ingredients
        )
        try:
            profile = db.session.get(HealthProfile, g.current_user.id)
            result = analyze_ingredient_list(ingredients, profile)
        except ValueError as exc:
            return jsonify({"message": str(exc)}), 400

        entry = ProductIngredientAnalysis(
            user_id=g.current_user.id,
            product_id=product.id,
            product_identity_snapshot=product.id,
            product_name_snapshot=product.name,
            ingredients_text=ingredients.strip(),
            analysis_result=result,
        )
        db.session.add(entry)
        db.session.commit()
        return jsonify({"analysis": _analysis_json(entry)}), 201
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception("Could not save ingredient analysis.")
        return jsonify({"message": "Could not save ingredient analysis. Please try again."}), 500
