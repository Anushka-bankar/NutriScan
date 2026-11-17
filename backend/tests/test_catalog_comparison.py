import sys
import unittest
import uuid
from decimal import Decimal
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402
from app.models import PackagedFoodCatalog  # noqa: E402


class CatalogComparisonTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app(
            {
                "TESTING": True,
                "JWT_SECRET_KEY": "catalog-comparison-test-secret-32-bytes",
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
                "full_name": "Catalog Comparison Test",
                "email": f"catalog-comparison-{uuid.uuid4().hex}@example.test",
                "password": "Catalog-comparison-test-password-42",
            },
        )
        if response.status_code != 201:
            raise RuntimeError(
                f"Could not create comparison test account: {response.get_json()}"
            )
        cls.auth = {"Authorization": f"Bearer {response.get_json()['token']}"}

        with cls.app.app_context():
            db.session.add_all(
                [
                    cls._product(
                        1,
                        "Selected biscuits",
                        "Brand A",
                        "BISCUIT",
                        "COOKIES",
                        30,
                        calories="150",
                        sugar="9",
                        saturated_fat="3",
                        sodium="90",
                        protein="3",
                        fiber="1",
                    ),
                    cls._product(
                        2,
                        "Similar biscuits",
                        "Brand B",
                        "BISCUIT",
                        "COOKIES",
                        60,
                        calories="240",
                        sugar="12",
                        saturated_fat="3",
                        sodium="180",
                        protein="8",
                        fiber="5",
                    ),
                    cls._product(
                        3,
                        "Digestive biscuits",
                        "Brand C",
                        "BISCUIT",
                        "DIGESTIVE",
                        40,
                        calories="180",
                        sugar="16",
                        saturated_fat="4",
                        sodium="100",
                        protein="2",
                        fiber="4",
                    ),
                    cls._product(
                        4,
                        "Cookie snacks",
                        "Brand D",
                        "SNACKS",
                        "COOKIES",
                        30,
                        calories="120",
                        sugar=None,
                        saturated_fat=None,
                        sodium=None,
                        protein="4",
                        fiber=None,
                    ),
                    cls._product(
                        5,
                        "Incomplete cookie",
                        "Brand E",
                        "BISCUIT",
                        "COOKIES",
                        30,
                        calories="120",
                        sugar=None,
                        saturated_fat=None,
                        sodium=None,
                        protein=None,
                        fiber=None,
                    ),
                    cls._product(
                        6,
                        "Per-hundred-gram cereal",
                        "Brand F",
                        "CEREAL",
                        "OATS",
                        50,
                        calories="350",
                        sugar="5",
                        saturated_fat="2",
                        sodium="100",
                        protein="10",
                        fiber="8",
                        nutrition_basis="per_100g",
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
        serving_size,
        calories,
        sugar,
        saturated_fat,
        sodium,
        protein,
        fiber,
        nutrition_basis="per_serving_inferred",
    ):
        return PackagedFoodCatalog(
            source_name=f"catalog_comparison_test_{id(cls)}",
            source_row_id=source_row_id,
            source_file_sha256="b" * 64,
            source_row_sha256=f"{source_row_id:064d}",
            product_name=name,
            brand_name=brand,
            category=category,
            sub_category=subcategory,
            ingredients=f"Ingredients for {name}",
            serving_size_g=Decimal(str(serving_size)),
            calories_kcal_per_serving=Decimal(calories) if calories is not None else None,
            carbohydrates_g_per_serving=Decimal("20"),
            protein_g_per_serving=Decimal(protein) if protein is not None else None,
            total_fat_g_per_serving=Decimal("5"),
            saturated_fat_g_per_serving=(
                Decimal(saturated_fat) if saturated_fat is not None else None
            ),
            trans_fat_g_per_serving=None,
            sugar_g_per_serving=Decimal(sugar) if sugar is not None else None,
            sodium_mg_per_serving=Decimal(sodium) if sodium is not None else None,
            dietary_fiber_g_per_serving=Decimal(fiber) if fiber is not None else None,
            cholesterol_mg_per_serving=None,
            calcium_mg_per_serving=None,
            iron_mg_per_serving=None,
            vitamin_details=None,
            price_inr=Decimal("20"),
            source_of_data="Test source",
            collected_by="Test collector",
            remarks=None,
            nutrition_basis=nutrition_basis,
            source_row_raw={
                "Item name": name,
                "Sugar_g": "" if sugar is None else str(sugar),
            },
            quality_flags={},
        )

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            db.drop_all()
            db.session.remove()
            db.engine.dispose()

    def test_comparison_normalizes_different_servings_and_preserves_source_data(self):
        response = self.client.get(
            "/api/catalog/products/compare?product_id_1=1&product_id_2=2",
            headers=self.auth,
        )
        self.assertEqual(response.status_code, 200, response.get_json())
        data = response.get_json()
        self.assertEqual(data["product_1"]["name"], "Selected biscuits")
        self.assertEqual(data["product_1"]["brand"], "Brand A")
        self.assertEqual(data["product_1"]["ingredients"], "Ingredients for Selected biscuits")
        self.assertEqual(data["product_1"]["nutrition_per_serving"]["trans_fat_g"], None)
        self.assertIn("calcium_mg", data["comparison"]["nutrients"])
        self.assertIn("iron_mg", data["comparison"]["nutrients"])
        comparison = data["comparison"]
        self.assertEqual(comparison["serving_size_relation"], "different")
        self.assertFalse(comparison["per_serving_values_comparable"])
        self.assertTrue(comparison["per_100g_normalization_possible"])
        calories = comparison["nutrients"]["calories_kcal"]
        self.assertEqual(calories["product_1_per_100g_comparable"], 500.0)
        self.assertEqual(calories["product_2_per_100g_comparable"], 400.0)
        self.assertEqual(
            calories["difference_per_100g_product_2_minus_product_1"],
            -100.0,
        )
        self.assertIn(
            "Serving sizes differ",
            " ".join(comparison["notes"]),
        )

    def test_missing_nutrients_remain_unavailable_in_comparison(self):
        response = self.client.get(
            "/api/catalog/products/compare?product_id_1=1&product_id_2=5",
            headers=self.auth,
        )
        self.assertEqual(response.status_code, 200, response.get_json())
        data = response.get_json()
        self.assertIsNone(data["product_2"]["nutrition_per_serving"]["sugar_g"])
        self.assertEqual(data["product_2"]["source_row_raw"]["Sugar_g"], "")
        sugar = data["comparison"]["nutrients"]["sugar_g"]
        self.assertIsNone(sugar["difference_per_100g_product_2_minus_product_1"])
        self.assertFalse(sugar["per_100g_comparable"])

    def test_comparison_flags_different_measurement_bases(self):
        response = self.client.get(
            "/api/catalog/products/compare?product_id_1=1&product_id_2=6",
            headers=self.auth,
        )
        self.assertEqual(response.status_code, 200, response.get_json())
        data = response.get_json()
        comparison = data["comparison"]
        self.assertFalse(comparison["measurement_bases_match"])
        self.assertFalse(comparison["per_serving_values_comparable"])
        self.assertTrue(comparison["per_100g_normalization_possible"])
        self.assertEqual(
            data["product_2"]["nutrition_per_100g_comparison_basis"],
            "source_per_100g",
        )
        self.assertTrue(any("Measurement bases differ" in note for note in comparison["notes"]))

    def test_comparison_validates_ids_and_missing_products(self):
        invalid_queries = (
            "/api/catalog/products/compare",
            "/api/catalog/products/compare?product_id_1=1",
            "/api/catalog/products/compare?product_id_1=nope&product_id_2=2",
            "/api/catalog/products/compare?product_id_1=-1&product_id_2=2",
            "/api/catalog/products/compare?product_id_1=1&product_id_2=1",
            "/api/catalog/products/compare?product_id_1=1&product_id_2=2&extra=1",
        )
        for path in invalid_queries:
            with self.subTest(path=path):
                response = self.client.get(path, headers=self.auth)
                self.assertEqual(response.status_code, 400, response.get_json())
                self.assertIn("message", response.get_json())

        missing = self.client.get(
            "/api/catalog/products/compare?product_id_1=1&product_id_2=999999",
            headers=self.auth,
        )
        self.assertEqual(missing.status_code, 404)

    def test_alternatives_use_categories_explanations_and_no_score(self):
        response = self.client.get(
            "/api/catalog/products/1/alternatives?limit=10",
            headers=self.auth,
        )
        self.assertEqual(response.status_code, 200, response.get_json())
        data = response.get_json()
        recommendations = data["recommendations"]
        ids = [item["product"]["id"] for item in recommendations]
        self.assertNotIn(1, ids)
        self.assertEqual(len(ids), len(set(ids)))
        self.assertNotIn(5, ids)
        self.assertEqual(ids[0], 2)
        self.assertTrue(
            any(
                "Calories is 100.0 kcal lower per 100 g." in item["why_suggested"]
                for item in recommendations
                if item["product"]["id"] == 2
            )
        )
        self.assertTrue(
            any(
                item["category_match"] == "same_subcategory_across_categories"
                for item in recommendations
                if item["product"]["id"] == 4
            )
        )
        self.assertTrue(
            any(
                "Not compared because data was unavailable" in reason
                for item in recommendations
                if item["product"]["id"] == 4
                for reason in item["why_suggested"]
            )
        )
        digestive = next(
            item for item in recommendations if item["product"]["id"] == 3
        )
        self.assertTrue(
            any(reason.startswith("Trade-off: Sugar is ") for reason in digestive["why_suggested"])
        )
        self.assertNotIn("nutrition_score", data)
        self.assertIn("not medical advice", data["logic"]["disclaimer"])

    def test_alternative_limit_and_missing_selected_product(self):
        for path in (
            "/api/catalog/products/1/alternatives?limit=0",
            "/api/catalog/products/1/alternatives?limit=21",
            "/api/catalog/products/1/alternatives?limit=abc",
            "/api/catalog/products/1/alternatives?limit=2&limit=3",
            "/api/catalog/products/1/alternatives?unknown=1",
        ):
            with self.subTest(path=path):
                response = self.client.get(path, headers=self.auth)
                self.assertEqual(response.status_code, 400, response.get_json())

        missing = self.client.get(
            "/api/catalog/products/999999/alternatives",
            headers=self.auth,
        )
        self.assertEqual(missing.status_code, 404)

    def test_catalog_and_existing_product_apis_still_work(self):
        catalog_response = self.client.get(
            "/api/catalog/products?q=selected",
            headers=self.auth,
        )
        product_response = self.client.get(
            "/api/products?q=not-found",
            headers=self.auth,
        )
        self.assertEqual(catalog_response.status_code, 200)
        self.assertEqual(product_response.status_code, 200)
        self.assertEqual(product_response.get_json()["products"], [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
