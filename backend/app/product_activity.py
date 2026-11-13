from flask import Blueprint, current_app, g, jsonify, request
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.auth import token_required
from app.extensions import db
from app.models import Product, ProductAnalysisHistory, ProductWatchlist
from app.products import NUTRIENT_FIELDS, _product_json

activity_bp = Blueprint("product_activity", __name__)


def _visible_products(product_id):
    return db.session.execute(
        select(Product).where(
            Product.id == product_id,
            Product.created_by == g.current_user.id,
        )
    ).scalar_one_or_none()


def _activity_json(entry, timestamp_field):
    snapshot = dict(entry.product_snapshot)
    if "id" not in snapshot:
        snapshot["id"] = None
    return {
        "id": entry.id,
        "product_id": entry.product_id,
        "product_available": entry.product_id is not None,
        "product": snapshot,
        timestamp_field: getattr(entry, timestamp_field).isoformat(),
    }


def _filtered_activity(model, timestamp_field):
    term = request.args.get("q", "").strip().casefold()
    category = request.args.get("category", "").strip()
    order = request.args.get("order", "newest")
    if len(term) > 100:
        return None, "Search term must be at most 100 characters."
    if category and len(category) > 50:
        return None, "Category filter must be at most 50 characters."
    if order not in {"newest", "oldest"}:
        return None, "Order must be newest or oldest."

    limit_value = request.args.get("limit", "50")
    try:
        limit = int(limit_value)
    except (TypeError, ValueError):
        return None, "Limit must be an integer between 1 and 100."
    if not 1 <= limit <= 100:
        return None, "Limit must be an integer between 1 and 100."

    query = select(model).where(model.user_id == g.current_user.id)
    if term:
        product_name = func.json_unquote(
            func.json_extract(model.product_snapshot, "$.name")
        )
        query = query.where(product_name.ilike(f"%{term}%"))
    if category:
        product_category = func.json_unquote(
            func.json_extract(model.product_snapshot, "$.category")
        )
        query = query.where(product_category == category)

    timestamp = getattr(model, timestamp_field)
    query = query.order_by(
        timestamp.asc() if order == "oldest" else timestamp.desc(),
        model.id.asc() if order == "oldest" else model.id.desc(),
    ).limit(limit)
    return db.session.execute(query).scalars().all(), None


@activity_bp.post("/products/<int:product_id>/history")
@token_required
def record_analysis(product_id):
    product = _visible_products(product_id)
    if product is None:
        return jsonify({"message": "Product not found."}), 404

    entry = ProductAnalysisHistory(
        user_id=g.current_user.id,
        product_id=product.id,
        product_snapshot=_product_json(product),
    )
    try:
        db.session.add(entry)
        db.session.commit()
        return jsonify({"history_entry": _activity_json(entry, "analyzed_at")}), 201
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception("Could not record product analysis history.")
        return jsonify({"message": "Could not record this analysis. Please try again."}), 500


@activity_bp.get("/history")
@token_required
def get_history():
    try:
        entries, error = _filtered_activity(ProductAnalysisHistory, "analyzed_at")
        if error:
            return jsonify({"message": error}), 400
        return jsonify(
            {"history": [_activity_json(entry, "analyzed_at") for entry in entries]}
        )
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception("Could not load product analysis history.")
        return jsonify({"message": "Could not load history. Please try again."}), 500


@activity_bp.get("/watchlist")
@token_required
def get_watchlist():
    try:
        entries, error = _filtered_activity(ProductWatchlist, "added_at")
        if error:
            return jsonify({"message": error}), 400
        return jsonify(
            {"watchlist": [_activity_json(entry, "added_at") for entry in entries]}
        )
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception("Could not load product watchlist.")
        return jsonify({"message": "Could not load watchlist. Please try again."}), 500


@activity_bp.get("/watchlist/status/<int:product_id>")
@token_required
def watchlist_status(product_id):
    product = _visible_products(product_id)
    if product is None:
        return jsonify({"message": "Product not found."}), 404
    entry = db.session.execute(
        select(ProductWatchlist).where(
            ProductWatchlist.user_id == g.current_user.id,
            ProductWatchlist.product_id == product_id,
        )
    ).scalar_one_or_none()
    return jsonify(
        {
            "saved": entry is not None,
            "entry_id": entry.id if entry is not None else None,
        }
    )


@activity_bp.post("/watchlist/<int:product_id>")
@token_required
def add_to_watchlist(product_id):
    product = _visible_products(product_id)
    if product is None:
        return jsonify({"message": "Product not found."}), 404

    existing = db.session.execute(
        select(ProductWatchlist).where(
            ProductWatchlist.user_id == g.current_user.id,
            ProductWatchlist.product_id == product.id,
        )
    ).scalar_one_or_none()
    if existing is not None:
        return jsonify(
            {
                "message": "Product is already in your watchlist.",
                "watchlist_entry": _activity_json(existing, "added_at"),
            }
        ), 200

    entry = ProductWatchlist(
        user_id=g.current_user.id,
        product_id=product.id,
        product_snapshot=_product_json(product),
    )
    try:
        db.session.add(entry)
        db.session.commit()
        return jsonify(
            {
                "message": "Product added to your watchlist.",
                "watchlist_entry": _activity_json(entry, "added_at"),
            }
        ), 201
    except IntegrityError:
        db.session.rollback()
        existing = db.session.execute(
            select(ProductWatchlist).where(
                ProductWatchlist.user_id == g.current_user.id,
                ProductWatchlist.product_id == product.id,
            )
        ).scalar_one_or_none()
        if existing is None:
            current_app.logger.exception("Watchlist insert conflicted unexpectedly.")
            return jsonify({"message": "Could not update your watchlist."}), 500
        return jsonify(
            {
                "message": "Product is already in your watchlist.",
                "watchlist_entry": _activity_json(existing, "added_at"),
            }
        ), 200
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception("Could not add product to watchlist.")
        return jsonify({"message": "Could not update your watchlist."}), 500


@activity_bp.delete("/watchlist/entries/<int:entry_id>")
@token_required
def remove_watchlist_entry(entry_id):
    entry = db.session.execute(
        select(ProductWatchlist).where(
            ProductWatchlist.id == entry_id,
            ProductWatchlist.user_id == g.current_user.id,
        )
    ).scalar_one_or_none()
    if entry is None:
        return jsonify({"message": "Watchlist entry not found."}), 404
    try:
        db.session.delete(entry)
        db.session.commit()
        return jsonify({"message": "Product removed from your watchlist."})
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception("Could not remove watchlist entry.")
        return jsonify({"message": "Could not update your watchlist."}), 500


@activity_bp.get("/products/compare")
@token_required
def compare_products():
    raw_ids = request.args.get("ids", "")
    try:
        ids = [int(value) for value in raw_ids.split(",") if value]
    except ValueError:
        return jsonify({"message": "Product IDs must be integers."}), 400
    if len(ids) < 2 or len(ids) > 4 or len(set(ids)) != len(ids):
        return jsonify({"message": "Choose 2 to 4 distinct products to compare."}), 400

    try:
        products = db.session.execute(
            select(Product).where(
                Product.created_by == g.current_user.id,
                Product.id.in_(ids),
            )
        ).scalars().all()
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception("Could not compare saved products.")
        return jsonify({"message": "Could not compare products. Please try again."}), 500
    by_id = {product.id: product for product in products}
    if len(by_id) != len(ids):
        return jsonify({"message": "One or more products are unavailable."}), 404

    unit_by_field = {
        field: "mg" if field == "sodium_mg" else
        "kJ" if field == "energy_kj" else
        "kcal" if field == "calories_kcal" else "g"
        for field in NUTRIENT_FIELDS
    }
    return jsonify(
        {
            "products": [_product_json(by_id[product_id]) for product_id in ids],
            "nutrients": [
                {
                    "field": field,
                    "label": label,
                    "unit": unit_by_field[field],
                    "values": [
                        float(getattr(by_id[product_id], field))
                        if getattr(by_id[product_id], field) is not None
                        else None
                        for product_id in ids
                    ],
                }
                for field, (label, _) in NUTRIENT_FIELDS.items()
            ],
        }
    )


@activity_bp.delete("/products/<int:product_id>")
@token_required
def delete_product(product_id):
    product = _visible_products(product_id)
    if product is None:
        return jsonify({"message": "Product not found."}), 404
    try:
        db.session.delete(product)
        db.session.commit()
        return jsonify({"message": "Product deleted. Saved history snapshots are preserved."})
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception("Could not delete product.")
        return jsonify({"message": "Could not delete product. Please try again."}), 500
