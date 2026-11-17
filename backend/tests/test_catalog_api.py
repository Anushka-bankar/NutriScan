import sys
import unittest
import uuid
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from sqlalchemy.exc import SQLAlchemyError

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402
from app.models import PackagedFoodCatalog  # noqa: E402


class CatalogApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app(
            {
                "TESTING": True,
                "JWT_SECRET_KEY": "catalog-api-test-secret-with-32-bytes",
                "SQLALCHEMY_DATABASE_URI": "sqlite://",
                "SQLALCHEMY_ENGINE_OPTIONS": {},
            }
        )
        cls.client = cls.app.test_client()
        with cls.app.app_context():
            db.create_all()

        response = cls.client.post(
            "/api/auth/register",
            json={
                "full_name": "Catalog API Test",
                "email": f"catalog-api-{uuid.uuid4().hex}@example.test",
                "password": "Catalog-api-test-password-42",
            },
        )
        if response.status_code != 201:
            raise RuntimeError(f"Could not create catalog test account: {response.get_json()}")
        cls.auth = {"Authorization": f"Bearer {response.get_json()['token']}"}

        with cls.app.app_context():
            db.session.add_all(
                [
                    cls._product(
                        1,
                        "Oats Breakfast",
                        "Nature Mill",
                        "SNACKS",
                        "CEREAL",
                        calories=Decimal("120"),
                        sugar=Decimal("5"),
                        fat=Decimal("3"),
                        protein=Decimal("4"),
                        sodium=Decimal("40"),
                        ingredients="Oats, honey",
                        raw_protein="4",
                    ),
                    cls._product(
                        2,
                        "Oats Bar",
                        "Daily Mill",
                        "SNACKS",
                        "BARS",
                        calories=Decimal("220"),
                        sugar=None,
                        fat=Decimal("8"),
                        protein=None,
                        sodium=None,
                        ingredients="Oats, seeds",
                        raw_protein="<1",
                    ),
                    cls._product(
                        3,
                        "Cocoa Drink",
                        "Nature Mill",
                        "BEVERAGES",
                        "DRINKS",
                        calories=Decimal("80"),
                        sugar=Decimal("9"),
                        fat=Decimal("1"),
                        protein=Decimal("2"),
                        sodium=Decimal("35"),
                        ingredients="Milk, cocoa",
                        raw_protein="2",
                    ),
                    cls._product(
                        4,
                        "Plain Rice",
                        None,
                        "GRAINS",
                        None,
                        calories=Decimal("350"),
                        sugar=Decimal("0"),
                        fat=Decimal("1"),
                        protein=Decimal("7"),
                        sodium=Decimal("2"),
                        ingredients=None,
                        raw_protein="7",
                    ),
                ]
            )
            db.session.commit()

    @classmethod
    def _product(
        cls,
        source_row_id,
        name,
        brand,
        category,
        subcategory,
        calories,
        sugar,
        fat,
        protein,
        sodium,
        ingredients,
        raw_protein,
    ):
        return PackagedFoodCatalog(
            source_name=f"catalog_api_test_{id(cls)}",
            source_row_id=source_row_id,
            source_file_sha256="a" * 64,
            source_row_sha256=f"{source_row_id:064d}",
            product_name=name,
            brand_name=brand,
            category=category,
            sub_category=subcategory,
            ingredients=ingredients,
            serving_size_g=Decimal("30"),
            calories_kcal_per_serving=calories,
            carbohydrates_g_per_serving=Decimal("20"),
            protein_g_per_serving=protein,
            total_fat_g_per_serving=fat,
            saturated_fat_g_per_serving=Decimal("1"),
            trans_fat_g_per_serving=Decimal("0"),
            sugar_g_per_serving=sugar,
            sodium_mg_per_serving=sodium,
            dietary_fiber_g_per_serving=Decimal("2"),
            cholesterol_mg_per_serving=None,
            calcium_mg_per_serving=None,
            iron_mg_per_serving=None,
            vitamin_details="",
            price_inr=Decimal("25"),
            source_of_data="Test source",
            collected_by="Test collector",
            remarks="Test provenance",
            nutrition_basis="per_serving_inferred",
            source_row_raw={"Proteins_g": raw_protein},
            quality_flags={"numeric_fields": {"Proteins_g": {"status": "exact"}}},
        )

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            db.drop_all()
            db.session.remove()
            db.engine.dispose()

    def test_listing_name_search_pagination_and_authentication(self):
        unauthenticated = self.client.get("/api/catalog/products")
        self.assertEqual(unauthenticated.status_code, 401)

        search = self.client.get(
            "/api/catalog/products?q=oats",
            headers=self.auth,
        )
        self.assertEqual(search.status_code, 200, search.get_json())
        self.assertEqual(
            [product["name"] for product in search.get_json()["products"]],
            ["Oats Bar", "Oats Breakfast"],
        )
        self.assertEqual(search.get_json()["pagination"]["total"], 2)

        paginated = self.client.get(
            "/api/catalog/products?page=2&per_page=1",
            headers=self.auth,
        )
        self.assertEqual(paginated.status_code, 200, paginated.get_json())
        self.assertEqual(
            [product["name"] for product in paginated.get_json()["products"]],
            ["Oats Bar"],
        )
        self.assertEqual(paginated.get_json()["pagination"]["pages"], 4)

    def test_brand_search(self):
        response = self.client.get(
            "/api/catalog/products?brand=nature",
            headers=self.auth,
        )
        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertEqual(
            {product["name"] for product in response.get_json()["products"]},
            {"Cocoa Drink", "Oats Breakfast"},
        )

    def test_product_details_include_ingredients_nutrition_and_provenance(self):
        response = self.client.get("/api/catalog/products/2", headers=self.auth)
        self.assertEqual(response.status_code, 200, response.get_json())
        product = response.get_json()["product"]
        self.assertEqual(product["ingredients"], "Oats, seeds")
        self.assertEqual(product["nutrition_per_serving"]["calories_kcal"], 220.0)
        self.assertIsNone(product["nutrition_per_serving"]["protein_g"])
        self.assertEqual(product["nutrition_basis"], "per_serving_inferred")
        self.assertEqual(product["source_row_raw"]["Proteins_g"], "<1")
        self.assertEqual(product["provenance"]["source_of_data"], "Test source")

    def test_categories_include_subcategories(self):
        response = self.client.get("/api/catalog/categories", headers=self.auth)
        self.assertEqual(response.status_code, 200, response.get_json())
        categories = {
            entry["name"]: entry["subcategories"]
            for entry in response.get_json()["categories"]
        }
        self.assertEqual(categories["SNACKS"], ["BARS", "CEREAL"])
        self.assertEqual(categories["GRAINS"], [])
        self.assertEqual(categories["BEVERAGES"], ["DRINKS"])

    def test_nutrition_filters_exclude_missing_values(self):
        response = self.client.get(
            "/api/catalog/products/filter"
            "?category=snacks&calories_min=100&calories_max=150&sugar_max=6",
            headers=self.auth,
        )
        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertEqual(
            [product["name"] for product in response.get_json()["products"]],
            ["Oats Breakfast"],
        )

        missing_sugar = self.client.get(
            "/api/catalog/products/filter?sugar_min=0",
            headers=self.auth,
        )
        self.assertEqual(missing_sugar.status_code, 200, missing_sugar.get_json())
        names = {product["name"] for product in missing_sugar.get_json()["products"]}
        self.assertNotIn("Oats Bar", names)

    def test_invalid_query_parameters_return_validation_errors(self):
        invalid_requests = (
            "/api/catalog/products?page=0",
            "/api/catalog/products?per_page=101",
            "/api/catalog/products?q=",
            "/api/catalog/products?q=oats&q=bar",
            "/api/catalog/products?unexpected=value",
            "/api/catalog/products/filter?calories_min=-1",
            "/api/catalog/products/filter?protein_max=NaN",
            "/api/catalog/products/filter?fat_min=5&fat_max=1",
            "/api/catalog/products/filter?sodium_max=abc",
        )
        for path in invalid_requests:
            with self.subTest(path=path):
                response = self.client.get(path, headers=self.auth)
                self.assertEqual(response.status_code, 400, response.get_json())
                self.assertIn("message", response.get_json())

    def test_missing_product_returns_404(self):
        response = self.client.get("/api/catalog/products/999999", headers=self.auth)
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.get_json()["message"], "Catalog product not found.")

    def test_database_errors_return_consistent_json(self):
        with self.app.app_context():
            with patch(
                "app.catalog.db.session.execute",
                side_effect=SQLAlchemyError("simulated database failure"),
            ):
                response = self.client.get(
                    "/api/catalog/products",
                    headers=self.auth,
                )
        self.assertEqual(response.status_code, 500)
        self.assertEqual(
            response.get_json(),
            {"message": "Could not load catalog products. Please try again."},
        )

    def test_existing_product_api_route_remains_available(self):
        response = self.client.get(
            "/api/products?q=not-found",
            headers=self.auth,
        )
        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertEqual(response.get_json()["products"], [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
