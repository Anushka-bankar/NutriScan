from decimal import Decimal, InvalidOperation
import json
import re
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from flask import Blueprint, current_app, g, jsonify, request
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.auth import token_required
from app.extensions import db
from app.models import Product
from app.product_options import PRODUCT_CATEGORIES, PRODUCT_DIETARY_TAGS

products_bp = Blueprint("products", __name__)

NUTRIENT_FIELDS = {
    "energy_kj": ("Energy", Decimal("3766")),
    "calories_kcal": ("Calories", Decimal("900")),
    "carbohydrates_g": ("Carbohydrates", Decimal("100")),
    "sugars_g": ("Total sugar", Decimal("100")),
    "protein_g": ("Protein", Decimal("100")),
    "total_fat_g": ("Total fat", Decimal("100")),
    "saturated_fat_g": ("Saturated fat", Decimal("100")),
    "fibre_g": ("Fibre", Decimal("100")),
    "sodium_mg": ("Sodium", Decimal("100000")),
}
PRODUCT_INPUT_FIELDS = tuple(NUTRIENT_FIELDS)
BARCODE_PATTERN = re.compile(r"^(?:\d{8}|\d{12,14})$")
OPEN_FOOD_FACTS_FIELDS = (
    "product_name,product_name_en,brands,quantity,serving_size,ingredients_text,"
    "ingredients_text_en,image_url,image_front_url,nutriments,categories_tags,"
    "ingredients_analysis_tags"
)


class ProductLookupError(Exception):
    pass


class ProductNotFoundError(ProductLookupError):
    pass


def _as_finite_float(value):
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if result >= 0 and result < float("inf") else None


def _off_category(tags):
    normalized = " ".join(tags).lower()
    category_tokens = (
        ("dairy_alternatives", ("plant-based-milk", "dairy-alternatives")),
        ("grains_cereals", ("cereals", "grains")),
        ("beverages", ("beverages", "drinks")),
        ("snacks", ("snacks",)),
        ("dairy", ("dairies", "dairy-products")),
        ("meat_poultry", ("meats", "poultry")),
        ("seafood", ("seafood", "fishes")),
        ("plant_protein", ("plant-based-foods", "plant-proteins")),
        ("fruits_vegetables", ("fruits", "vegetables")),
        ("condiments_sauces", ("condiments", "sauces")),
        ("prepared_meals", ("prepared-meals",)),
        ("bakery", ("breads", "bakery")),
    )
    for category, tokens in category_tokens:
        if any(token in normalized for token in tokens):
            return category
    return "other"


def _safe_off_image(product):
    image = product.get("image_url") or product.get("image_front_url")
    if not isinstance(image, str) or len(image) > 500:
        return None
    try:
        parsed = urlparse(image)
    except ValueError:
        return None
    if parsed.scheme != "https" or parsed.hostname not in {
        "images.openfoodfacts.org",
        "static.openfoodfacts.org",
    }:
        return None
    return image


def _off_dietary_tags(tags):
    normalized = set(tags)
    result = []
    if "en:vegan" in normalized:
        result.extend(("vegan", "vegetarian"))
    elif "en:vegetarian" in normalized:
        result.append("vegetarian")
    return result


def _serving_grams(serving_text):
    if not isinstance(serving_text, str):
        return None
    match = re.search(r"(\d+(?:[.,]\d+)?)\s*g\b", serving_text, re.IGNORECASE)
    if not match:
        return None
    return _as_finite_float(match.group(1).replace(",", "."))


def _open_food_facts_product(barcode):
    if not isinstance(barcode, str) or not BARCODE_PATTERN.fullmatch(barcode):
        raise ValueError("Enter a valid 8, 12, 13, or 14-digit product barcode.")

    url = (
        f"https://world.openfoodfacts.org/api/v2/product/{barcode}.json"
        f"?fields={OPEN_FOOD_FACTS_FIELDS}"
    )
    provider_request = Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "NutriScan/0.1 (product nutrition lookup)",
        },
    )
    try:
        with urlopen(provider_request, timeout=8) as response:
            response_body = response.read(2_000_001)
    except HTTPError as exc:
        current_app.logger.warning("Open Food Facts returned HTTP %s.", exc.code)
        raise ProductLookupError(
            "The product database is temporarily unavailable. Try again later."
        ) from None
    except (URLError, TimeoutError, OSError):
        current_app.logger.warning("Open Food Facts lookup could not be completed.")
        raise ProductLookupError(
            "Could not reach the product database. Check your connection and try again."
        ) from None

    if len(response_body) > 2_000_000:
        raise ProductLookupError("The product database response was too large.")
    try:
        result = json.loads(response_body)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise ProductLookupError("The product database returned invalid data.") from None
    if not isinstance(result, dict):
        raise ProductLookupError("The product database returned invalid data.")
    if result.get("status") != 1 or not isinstance(result.get("product"), dict):
        raise ProductNotFoundError(
            "No product was found for this barcode. Try scanning the package label."
        )

    source = result["product"]
    nutriments = source.get("nutriments")
    if not isinstance(nutriments, dict):
        nutriments = {}
    name = source.get("product_name") or source.get("product_name_en") or ""
    if not isinstance(name, str):
        name = ""
    brands = source.get("brands")
    if not isinstance(brands, str):
        brands = ""
    ingredients = source.get("ingredients_text") or source.get("ingredients_text_en")
    if not isinstance(ingredients, str):
        ingredients = ""
    category_tags = source.get("categories_tags")
    dietary_tags = source.get("ingredients_analysis_tags")
    category_tags = (
        [tag for tag in category_tags if isinstance(tag, str)]
        if isinstance(category_tags, list)
        else []
    )
    dietary_tags = (
        [tag for tag in dietary_tags if isinstance(tag, str)]
        if isinstance(dietary_tags, list)
        else []
    )

    facts = {
        "energy_kj": _as_finite_float(nutriments.get("energy-kj_100g")),
        "calories_kcal": _as_finite_float(nutriments.get("energy-kcal_100g")),
        "carbohydrates_g": _as_finite_float(nutriments.get("carbohydrates_100g")),
        "sugars_g": _as_finite_float(nutriments.get("sugars_100g")),
        "protein_g": _as_finite_float(nutriments.get("proteins_100g")),
        "total_fat_g": _as_finite_float(nutriments.get("fat_100g")),
        "saturated_fat_g": _as_finite_float(nutriments.get("saturated-fat_100g")),
        "fibre_g": _as_finite_float(nutriments.get("fiber_100g")),
        "sodium_mg": (
            _as_finite_float(nutriments.get("sodium_100g")) * 1000
            if _as_finite_float(nutriments.get("sodium_100g")) is not None
            else None
        ),
    }
    return {
        "barcode": barcode,
        "name": name.strip()[:160],
        "brand": brands.strip()[:120] or None,
        "ingredients": ingredients.strip()[:10000] or None,
        "image_url": _safe_off_image(source),
        "category": _off_category(category_tags),
        "dietary_tags": _off_dietary_tags(dietary_tags),
        "serving_size_g": _serving_grams(source.get("serving_size")),
        **facts,
    }


def _save_scanned_product(user_id, values, source_type, source_label):
    product = Product(
        created_by=user_id,
        source_type=source_type,
        source_label=source_label,
        **values,
    )
    db.session.add(product)
    db.session.commit()
    return product


def _existing_barcode_product(user_id, barcode):
    if not barcode:
        return None
    return db.session.execute(
        select(Product).where(
            Product.created_by == user_id,
            Product.barcode == barcode,
        ).order_by(Product.id.asc()).limit(1)
    ).scalar_one_or_none()


def _decimal(value, field, maximum):
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError(f"{field} must be a valid number.") from None
    if not result.is_finite() or result < 0 or result > maximum:
        raise ValueError(f"{field} must be between 0 and {maximum}.")
    return result.quantize(Decimal("0.01"))


def validate_product(body, require_nutrition=True, require_name=True):
    name = body.get("name")
    brand = body.get("brand", "")
    if not isinstance(name, str) or (require_name and not name.strip()) or len(name.strip()) > 160:
        return None, "Product name is required and must be at most 160 characters."
    if brand is None:
        brand = ""
    if not isinstance(brand, str) or len(brand.strip()) > 120:
        return None, "Brand must be at most 120 characters."
    ingredients = body.get("ingredients")
    if ingredients is not None and (
        not isinstance(ingredients, str) or len(ingredients) > 10000
    ):
        return None, "Ingredients must be text of at most 10000 characters."
    packaging_text = body.get("packaging_text")
    if packaging_text is not None and (
        not isinstance(packaging_text, str) or len(packaging_text) > 20000
    ):
        return None, "Packaging text must be text of at most 20000 characters."
    image_url = body.get("image_url")
    if image_url is not None and (
        not isinstance(image_url, str)
        or len(image_url) > 500
        or not image_url.startswith("https://")
        or _safe_off_image({"image_url": image_url}) is None
    ):
        return None, "Product image must be an HTTPS Open Food Facts image URL."
    barcode = body.get("barcode")
    if barcode is not None and not BARCODE_PATTERN.fullmatch(str(barcode)):
        return None, "Enter a valid 8, 12, 13, or 14-digit product barcode."

    category = body.get("category")
    if category is not None and (
        not isinstance(category, str) or category not in PRODUCT_CATEGORIES
    ):
        return None, "Choose a valid product category."
    dietary_tags = body.get("dietary_tags", [])
    if (
        not isinstance(dietary_tags, list)
        or len(dietary_tags) > len(PRODUCT_DIETARY_TAGS)
        or any(
            not isinstance(tag, str) or tag not in PRODUCT_DIETARY_TAGS
            for tag in dietary_tags
        )
    ):
        return None, "Choose valid dietary suitability tags."

    values = {}
    for field, (label, maximum) in NUTRIENT_FIELDS.items():
        if field not in body or body[field] is None or body[field] == "":
            values[field] = None
            continue
        try:
            values[field] = _decimal(body[field], label, maximum)
        except ValueError as exc:
            return None, str(exc)
    if require_nutrition and all(value is None for value in values.values()):
        return None, "Enter at least one available nutrition value."
    if (
        values["sugars_g"] is not None
        and values["carbohydrates_g"] is not None
        and values["sugars_g"] > values["carbohydrates_g"]
    ):
        return None, "Total sugar cannot exceed carbohydrates."
    if (
        values["saturated_fat_g"] is not None
        and values["total_fat_g"] is not None
        and values["saturated_fat_g"] > values["total_fat_g"]
    ):
        return None, "Saturated fat cannot exceed total fat."

    serving_value = body.get("serving_size_g")
    serving_size = None
    if serving_value not in (None, ""):
        try:
            serving_size = _decimal(serving_value, "Serving size", Decimal("5000"))
        except ValueError as exc:
            return None, str(exc)
        if serving_size <= 0:
            return None, "Serving size must be greater than 0 grams."

    return {
        "name": name.strip(),
        "brand": brand.strip() or None,
        "barcode": str(barcode) if barcode is not None else None,
        "ingredients": ingredients.strip() or None if ingredients else None,
        "packaging_text": packaging_text.strip() or None if packaging_text else None,
        "image_url": image_url,
        "category": category,
        "dietary_tags": sorted(set(dietary_tags)),
        "serving_size_g": serving_size,
        **values,
    }, None


def _product_json(product, include_packaging_text=False):
    per_100g = {
        field: float(getattr(product, field)) if getattr(product, field) is not None else None
        for field in PRODUCT_INPUT_FIELDS
    }
    serving = None
    if product.serving_size_g is not None:
        multiplier = float(product.serving_size_g) / 100
        serving = {
            field: round(value * multiplier, 2) if value is not None else None
            for field, value in per_100g.items()
        }
    return {
        "id": product.id,
        "name": product.name,
        "brand": product.brand,
        "barcode": product.barcode,
        "ingredients": product.ingredients,
        **(
            {"packaging_text": product.packaging_text}
            if include_packaging_text
            else {}
        ),
        "image_url": product.image_url,
        "category": product.category,
        "category_label": PRODUCT_CATEGORIES.get(product.category, "Uncategorized"),
        "dietary_tags": product.dietary_tags or [],
        "serving_size_g": (
            float(product.serving_size_g)
            if product.serving_size_g is not None
            else None
        ),
        "nutrition_per_100g": per_100g,
        "nutrition_per_serving": serving,
        "source_type": product.source_type,
        "source_label": product.source_label,
        "created_at": product.created_at.isoformat() if product.created_at else None,
        "updated_at": product.updated_at.isoformat() if product.updated_at else None,
    }


def _owned_or_404(product_id):
    product = db.session.execute(
        select(Product).where(
            Product.id == product_id,
            Product.created_by == g.current_user.id,
        )
    ).scalar_one_or_none()
    return product


@products_bp.get("")
@token_required
def search_products():
    query = request.args.get("q", "").strip()
    if not query or len(query) < 2:
        return jsonify({"message": "Search term must be at least 2 characters."}), 400
    if len(query) > 100:
        return jsonify({"message": "Search term must be at most 100 characters."}), 400

    limit_value = request.args.get("limit", "20")
    try:
        limit = int(limit_value)
    except (TypeError, ValueError):
        return jsonify({"message": "Limit must be an integer between 1 and 50."}), 400
    if not 1 <= limit <= 50:
        return jsonify({"message": "Limit must be an integer between 1 and 50."}), 400

    products = db.session.execute(
        select(Product)
        .where(
            Product.created_by == g.current_user.id,
            Product.name.ilike(f"%{query}%"),
        )
        .order_by(Product.name.asc(), Product.id.asc())
        .limit(limit)
    ).scalars()
    return jsonify({"products": [_product_json(product) for product in products]})


@products_bp.post("")
@token_required
def create_product():
    if not request.is_json:
        return jsonify({"message": "A JSON request body is required."}), 400
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return jsonify({"message": "A JSON object is required."}), 400
    if body.get("packaging_text") not in (None, ""):
        return jsonify(
            {"message": "Package OCR text can only be saved through the OCR import."}
        ), 400

    values, error = validate_product(body)
    if error:
        return jsonify({"message": error}), 400
    existing = _existing_barcode_product(g.current_user.id, values["barcode"])
    if existing is not None:
        return jsonify(
            {
                "message": "A product with this barcode is already in your library.",
                "product": _product_json(existing),
                "already_saved": True,
            }
        ), 200

    product = Product(
        created_by=g.current_user.id,
        source_type="user_entered",
        source_label="User-entered; not independently verified",
        **values,
    )
    try:
        db.session.add(product)
        db.session.commit()
        return jsonify({"product": _product_json(product)}), 201
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception("Could not save product nutrition data.")
        return jsonify({"message": "Could not save product. Please try again."}), 500


@products_bp.get("/lookup/barcode/<barcode>")
@token_required
def lookup_barcode(barcode):
    if not BARCODE_PATTERN.fullmatch(barcode):
        return jsonify({"message": "Enter a valid product barcode."}), 400
    existing = _existing_barcode_product(g.current_user.id, barcode)
    if existing is not None:
        return jsonify(
            {
                "product": None,
                "existing_product": _product_json(existing),
            }
        )
    try:
        product = _open_food_facts_product(barcode)
        validated, validation_error = validate_product(
            product,
            require_nutrition=False,
            require_name=False,
        )
        if validation_error:
            raise ProductLookupError(
                "The barcode entry has inconsistent nutrition data. Scan the package label instead."
            )
        response_product = {
            key: float(value) if isinstance(value, Decimal) else value
            for key, value in validated.items()
        }
        return jsonify(
            {
                "product": {
                    **response_product,
                    "source_type": "open_food_facts",
                    "source_label": (
                        "Open Food Facts community data; review before saving"
                    ),
                },
                "existing_product": None,
            }
        )
    except ValueError as exc:
        return jsonify({"message": str(exc)}), 400
    except ProductNotFoundError as exc:
        return jsonify({"message": str(exc)}), 404
    except ProductLookupError as exc:
        return jsonify({"message": str(exc)}), 502


@products_bp.post("/import/barcode")
@token_required
def import_barcode_product():
    if not request.is_json:
        return jsonify({"message": "A JSON request body is required."}), 400
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return jsonify({"message": "A JSON object is required."}), 400
    try:
        barcode = body.get("barcode")
        if not isinstance(barcode, str) or not BARCODE_PATTERN.fullmatch(barcode):
            raise ValueError("Enter a valid product barcode.")
        existing = _existing_barcode_product(g.current_user.id, barcode)
        if existing is not None:
            return jsonify(
                {
                    "message": "This barcode is already in your product library.",
                    "product": _product_json(existing),
                    "already_saved": True,
                }
            ), 200
        values = _open_food_facts_product(barcode)
    except ValueError as exc:
        return jsonify({"message": str(exc)}), 400
    except ProductNotFoundError as exc:
        return jsonify({"message": str(exc)}), 404
    except ProductLookupError as exc:
        return jsonify({"message": str(exc)}), 502

    category = body.get("category", values["category"])
    if category not in PRODUCT_CATEGORIES:
        return jsonify({"message": "Choose a valid product category."}), 400
    values["category"] = category
    reviewed = body.get("reviewed_product")
    if reviewed is not None:
        if not isinstance(reviewed, dict):
            return jsonify({"message": "Reviewed product details must be an object."}), 400
        reviewed = {**values, **reviewed, "barcode": barcode}
        reviewed_values, validation_error = validate_product(
            reviewed,
            require_nutrition=False,
        )
        if validation_error:
            return jsonify({"message": validation_error}), 400
        if reviewed_values["packaging_text"] is not None:
            return jsonify(
                {"message": "Package OCR text can only be saved through the OCR import."}
            ), 400
        values = reviewed_values
        values["category"] = category
    values, validation_error = validate_product(values, require_nutrition=False)
    if validation_error:
        return jsonify(
            {
                "message": (
                    "The barcode entry has inconsistent nutrition data. "
                    "Scan the package label instead."
                )
            }
        ), 502
    review_confirmed = (
        isinstance(reviewed, dict) and reviewed.get("review_confirmed") is True
    ) or body.get("review_confirmed") is True
    if (
        values["serving_size_g"] is not None
        and (values["serving_size_g"] < 1 or values["serving_size_g"] > 1000)
        and not review_confirmed
    ):
        return jsonify(
            {
                "message": (
                    "Serving size looks unusual. Verify it and confirm the review "
                    "before saving."
                )
            }
        ), 400
    try:
        product = _save_scanned_product(
            g.current_user.id,
            values,
            "open_food_facts",
            "Open Food Facts community data; user-reviewed, not independently verified",
        )
        return jsonify({"product": _product_json(product)}), 201
    except IntegrityError:
        db.session.rollback()
        existing = _existing_barcode_product(g.current_user.id, barcode)
        if existing is not None:
            return jsonify(
                {
                    "message": "This barcode is already in your product library.",
                    "product": _product_json(existing),
                    "already_saved": True,
                }
            ), 200
        current_app.logger.exception("Could not save barcode product.")
        return jsonify({"message": "Could not save product. Please try again."}), 500
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception("Could not save barcode product.")
        return jsonify({"message": "Could not save product. Please try again."}), 500


@products_bp.post("/import/ocr")
@token_required
def import_ocr_product():
    if not request.is_json:
        return jsonify({"message": "A JSON request body is required."}), 400
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return jsonify({"message": "A JSON object is required."}), 400
    values, error = validate_product(body)
    if error:
        return jsonify({"message": error}), 400
    if values["category"] is None:
        return jsonify({"message": "Choose a food category before saving."}), 400
    existing = _existing_barcode_product(g.current_user.id, values["barcode"])
    if existing is not None:
        return jsonify(
            {
                "message": "A product with this barcode is already in your library.",
                "product": _product_json(existing),
                "already_saved": True,
            }
        ), 200
    serving_size = values["serving_size_g"]
    if (
        serving_size is not None
        and (serving_size < 1 or serving_size > 1000)
        and body.get("review_confirmed") is not True
    ):
        return jsonify(
            {
                "message": (
                    "Serving size looks unusual. Verify it and confirm the review "
                    "before saving."
                )
            }
        ), 400
    try:
        product = _save_scanned_product(
            g.current_user.id,
            values,
            "label_ocr",
            "OCR-extracted from package; user-reviewed, not independently verified",
        )
        return jsonify({"product": _product_json(product)}), 201
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception("Could not save OCR product.")
        return jsonify({"message": "Could not save product. Please try again."}), 500


@products_bp.get("/<int:product_id>")
@token_required
def get_product(product_id):
    product = _owned_or_404(product_id)
    if product is None:
        return jsonify({"message": "Product not found."}), 404
    return jsonify({"product": _product_json(product, include_packaging_text=True)})


@products_bp.patch("/<int:product_id>/classification")
@token_required
def classify_product(product_id):
    if not request.is_json:
        return jsonify({"message": "A JSON request body is required."}), 400
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return jsonify({"message": "A JSON object is required."}), 400
    category = body.get("category")
    dietary_tags = body.get("dietary_tags", [])
    if not isinstance(category, str) or category not in PRODUCT_CATEGORIES:
        return jsonify({"message": "Choose a valid product category."}), 400
    if (
        not isinstance(dietary_tags, list)
        or len(dietary_tags) > len(PRODUCT_DIETARY_TAGS)
        or any(
            not isinstance(tag, str) or tag not in PRODUCT_DIETARY_TAGS
            for tag in dietary_tags
        )
    ):
        return jsonify({"message": "Choose valid dietary suitability tags."}), 400

    product = _owned_or_404(product_id)
    if product is None:
        return jsonify({"message": "Product not found."}), 404
    product.category = category
    product.dietary_tags = sorted(set(dietary_tags))
    try:
        db.session.commit()
        return jsonify({"product": _product_json(product)})
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception("Could not save product classification.")
        return jsonify({"message": "Could not update product. Please try again."}), 500
