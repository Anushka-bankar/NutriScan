import re
from decimal import Decimal, InvalidOperation

from flask import Blueprint, current_app, jsonify, request
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError

from app.auth import token_required
from app.extensions import db
from app.models import PackagedFoodCatalog

catalog_bp = Blueprint("catalog", __name__)

MAX_PAGE = 1_000_000
MAX_PER_PAGE = 100
MAX_DECIMAL = Decimal("999999999999.999999")
POSITIVE_INTEGER = re.compile(r"^[0-9]+$")
NON_NEGATIVE_DECIMAL = re.compile(r"^(?:[0-9]+(?:\.[0-9]{1,6})?|\.[0-9]{1,6})$")

NUTRITION_FIELDS = {
    "calories_kcal": "calories_kcal_per_serving",
    "carbohydrates_g": "carbohydrates_g_per_serving",
    "protein_g": "protein_g_per_serving",
    "total_fat_g": "total_fat_g_per_serving",
    "saturated_fat_g": "saturated_fat_g_per_serving",
    "trans_fat_g": "trans_fat_g_per_serving",
    "sugar_g": "sugar_g_per_serving",
    "sodium_mg": "sodium_mg_per_serving",
    "dietary_fiber_g": "dietary_fiber_g_per_serving",
    "cholesterol_mg": "cholesterol_mg_per_serving",
    "calcium_mg": "calcium_mg_per_serving",
    "iron_mg": "iron_mg_per_serving",
}

FILTER_FIELDS = {
    "calories": "calories_kcal_per_serving",
    "sugar": "sugar_g_per_serving",
    "fat": "total_fat_g_per_serving",
    "protein": "protein_g_per_serving",
    "sodium": "sodium_mg_per_serving",
}


def _query_error(allowed_parameters):
    unknown = sorted(set(request.args.keys()) - allowed_parameters)
    if unknown:
        return f"Unsupported query parameter: {unknown[0]}."
    for parameter in request.args.keys():
        if len(request.args.getlist(parameter)) != 1:
            return f"Query parameter '{parameter}' may only be provided once."
    return None


def _pagination_values():
    values = {}
    for parameter, default, maximum in (
        ("page", 1, MAX_PAGE),
        ("per_page", 20, MAX_PER_PAGE),
    ):
        raw_value = request.args.get(parameter)
        if raw_value is None:
            values[parameter] = default
            continue
        if (
            len(raw_value) > 10
            or not POSITIVE_INTEGER.fullmatch(raw_value)
        ):
            return None, f"{parameter} must be a positive integer no greater than {maximum}."
        value = int(raw_value)
        if value < 1 or value > maximum:
            return None, f"{parameter} must be a positive integer no greater than {maximum}."
        values[parameter] = value
    return values, None


def _search_value(parameter, max_length):
    value = request.args.get(parameter)
    if value is None:
        return None, None
    value = value.strip()
    if not value:
        return None, f"{parameter} cannot be blank."
    if len(value) > max_length:
        return None, f"{parameter} must be at most {max_length} characters."
    return value, None


def _decimal_filter(parameter):
    raw_value = request.args.get(parameter)
    if raw_value is None:
        return None, None
    if len(raw_value) > 32 or not NON_NEGATIVE_DECIMAL.fullmatch(raw_value):
        return None, f"{parameter} must be a non-negative number with at most 6 decimal places."
    try:
        value = Decimal(raw_value)
    except InvalidOperation:
        return None, f"{parameter} must be a valid non-negative number."
    if not value.is_finite() or value > MAX_DECIMAL:
        return None, f"{parameter} is outside the supported numeric range."
    return value, None


def _escaped_contains(value):
    escaped = value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def _number(value):
    return float(value) if value is not None else None


def catalog_product_json(product, include_raw_values=False):
    result = {
        "id": product.id,
        "name": product.product_name,
        "brand": product.brand_name,
        "category": product.category,
        "subcategory": product.sub_category,
        "ingredients": product.ingredients,
        "serving_size_g": _number(product.serving_size_g),
        "nutrition_basis": product.nutrition_basis,
        "nutrition_per_serving": {
            public_name: _number(getattr(product, model_field))
            for public_name, model_field in NUTRITION_FIELDS.items()
        },
        "vitamin_details": product.vitamin_details,
        "price_inr": _number(product.price_inr),
        "provenance": {
            "source_name": product.source_name,
            "source_row_id": product.source_row_id,
            "source_file_sha256": product.source_file_sha256,
            "source_row_sha256": product.source_row_sha256,
            "source_of_data": product.source_of_data,
            "collection_date": (
                product.collection_date.isoformat()
                if product.collection_date is not None
                else None
            ),
            "collected_by": product.collected_by,
            "remarks": product.remarks,
        },
        "created_at": product.created_at.isoformat() if product.created_at else None,
        "updated_at": product.updated_at.isoformat() if product.updated_at else None,
    }
    if include_raw_values:
        result["source_row_raw"] = product.source_row_raw
        result["quality_flags"] = product.quality_flags
    return result


def _page_response(statement, page, per_page):
    total = db.session.execute(
        select(func.count()).select_from(statement.order_by(None).subquery())
    ).scalar_one()
    products = db.session.execute(
        statement.order_by(
            PackagedFoodCatalog.product_name.asc(),
            PackagedFoodCatalog.id.asc(),
        )
        .offset((page - 1) * per_page)
        .limit(per_page)
    ).scalars().all()
    return jsonify(
        {
            "products": [catalog_product_json(product) for product in products],
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total": total,
                "pages": (total + per_page - 1) // per_page,
            },
        }
    )


def _database_error(message):
    db.session.rollback()
    current_app.logger.exception("Could not retrieve packaged-food catalog data.")
    return jsonify({"message": message}), 500


@catalog_bp.get("/products")
@token_required
def list_catalog_products():
    allowed = {"page", "per_page", "q", "brand"}
    error = _query_error(allowed)
    if error:
        return jsonify({"message": error}), 400

    pagination, error = _pagination_values()
    if error:
        return jsonify({"message": error}), 400
    query, error = _search_value("q", 100)
    if error:
        return jsonify({"message": error}), 400
    brand, error = _search_value("brand", 150)
    if error:
        return jsonify({"message": error}), 400

    statement = select(PackagedFoodCatalog)
    if query is not None:
        statement = statement.where(
            PackagedFoodCatalog.product_name.ilike(
                _escaped_contains(query), escape="\\"
            )
        )
    if brand is not None:
        statement = statement.where(
            PackagedFoodCatalog.brand_name.ilike(
                _escaped_contains(brand), escape="\\"
            )
        )
    try:
        return _page_response(
            statement,
            pagination["page"],
            pagination["per_page"],
        )
    except SQLAlchemyError:
        return _database_error("Could not load catalog products. Please try again.")


@catalog_bp.get("/products/filter")
@token_required
def filter_catalog_products():
    allowed = {"page", "per_page", "category"}
    for field in FILTER_FIELDS:
        allowed.update({f"{field}_min", f"{field}_max"})
    error = _query_error(allowed)
    if error:
        return jsonify({"message": error}), 400

    pagination, error = _pagination_values()
    if error:
        return jsonify({"message": error}), 400
    category, error = _search_value("category", 100)
    if error:
        return jsonify({"message": error}), 400

    statement = select(PackagedFoodCatalog)
    if category is not None:
        statement = statement.where(
            func.lower(PackagedFoodCatalog.category) == category.lower()
        )

    for field, model_field in FILTER_FIELDS.items():
        column = getattr(PackagedFoodCatalog, model_field)
        minimum, error = _decimal_filter(f"{field}_min")
        if error:
            return jsonify({"message": error}), 400
        maximum, error = _decimal_filter(f"{field}_max")
        if error:
            return jsonify({"message": error}), 400
        if minimum is not None and maximum is not None and minimum > maximum:
            return jsonify(
                {"message": f"{field}_min cannot be greater than {field}_max."}
            ), 400
        if minimum is not None:
            statement = statement.where(column.is_not(None), column >= minimum)
        if maximum is not None:
            statement = statement.where(column.is_not(None), column <= maximum)

    try:
        return _page_response(
            statement,
            pagination["page"],
            pagination["per_page"],
        )
    except SQLAlchemyError:
        return _database_error("Could not filter catalog products. Please try again.")


@catalog_bp.get("/products/<int:product_id>")
@token_required
def get_catalog_product(product_id):
    if request.args:
        error = _query_error(set())
        return jsonify({"message": error}), 400
    try:
        product = db.session.execute(
            select(PackagedFoodCatalog).where(PackagedFoodCatalog.id == product_id)
        ).scalar_one_or_none()
    except SQLAlchemyError:
        return _database_error("Could not load catalog product. Please try again.")
    if product is None:
        return jsonify({"message": "Catalog product not found."}), 404
    return jsonify({"product": catalog_product_json(product, include_raw_values=True)})


@catalog_bp.get("/categories")
@token_required
def list_catalog_categories():
    if request.args:
        error = _query_error(set())
        return jsonify({"message": error}), 400
    try:
        rows = db.session.execute(
            select(
                PackagedFoodCatalog.category,
                PackagedFoodCatalog.sub_category,
            )
            .where(PackagedFoodCatalog.category.is_not(None))
            .distinct()
            .order_by(
                PackagedFoodCatalog.category.asc(),
                PackagedFoodCatalog.sub_category.asc(),
            )
        ).all()
    except SQLAlchemyError:
        return _database_error("Could not load catalog categories. Please try again.")

    categories = {}
    for category, subcategory in rows:
        categories.setdefault(category, set())
        if subcategory:
            categories[category].add(subcategory)
    return jsonify(
        {
            "categories": [
                {"name": name, "subcategories": sorted(subcategories)}
                for name, subcategories in sorted(categories.items())
            ]
        }
    )
