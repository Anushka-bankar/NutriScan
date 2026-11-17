import json
import sys
import unittest
import uuid
from pathlib import Path
from urllib.error import URLError
from unittest.mock import patch

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402
from app.models import Product, User  # noqa: E402


class ProductNutritionMySQLTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.client = cls.app.test_client()
        cls.users = []
        cls.tokens = []
        for index in range(2):
            email = f"product-test-{uuid.uuid4().hex}@example.test"
            response = cls.client.post(
                "/api/auth/register",
                json={
                    "full_name": f"Product Test {index}",
                    "email": email,
                    "password": "Product-test-password-42",
                },
            )
            if response.status_code != 201:
                raise RuntimeError(
                    f"Could not create product integration account: {response.get_json()}"
                )
            data = response.get_json()
            cls.users.append(data["user"])
            cls.tokens.append(data["token"])

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            for user_data in cls.users:
                user = db.session.get(User, user_data["id"])
                if user is not None:
                    db.session.delete(user)
            db.session.commit()
            db.session.remove()

    def test_create_search_retrieve_validation_and_ownership(self):
        auth = {"Authorization": f"Bearer {self.tokens[0]}"}
        other_auth = {"Authorization": f"Bearer {self.tokens[1]}"}
        values = {
            "name": "Test rolled oats",
            "brand": "Example Pantry",
            "category": "grains_cereals",
            "dietary_tags": ["vegetarian"],
            "serving_size_g": 40,
            "energy_kj": 1580,
            "calories_kcal": 379,
            "carbohydrates_g": 67,
            "sugars_g": 1,
            "protein_g": 13,
            "total_fat_g": 7,
            "saturated_fat_g": 1.2,
            "fibre_g": 10,
            "sodium_mg": 6,
        }

        unauthenticated = self.client.get("/api/products?q=oats")
        self.assertEqual(unauthenticated.status_code, 401)
        too_short = self.client.get("/api/products?q=o", headers=auth)
        self.assertEqual(too_short.status_code, 400)
        invalid_limit = self.client.get(
            "/api/products?q=oats&limit=0", headers=auth
        )
        self.assertEqual(invalid_limit.status_code, 400)

        invalid_nutrition = self.client.post(
            "/api/products",
            json={**values, "sugars_g": 70},
            headers=auth,
        )
        self.assertEqual(invalid_nutrition.status_code, 400)

        created = self.client.post("/api/products", json=values, headers=auth)
        self.assertEqual(created.status_code, 201, created.get_json())
        product = created.get_json()["product"]
        self.assertEqual(product["source_type"], "user_entered")
        self.assertIn("not independently verified", product["source_label"])
        self.assertEqual(product["category"], "grains_cereals")
        self.assertEqual(product["nutrition_per_100g"]["calories_kcal"], 379)
        self.assertEqual(product["nutrition_per_serving"]["calories_kcal"], 151.6)
        self.assertEqual(product["nutrition_per_serving"]["sodium_mg"], 2.4)
        product_id = product["id"]

        with self.app.app_context():
            stored = db.session.get(Product, product_id)
            self.assertIsNotNone(stored)
            self.assertEqual(stored.name, values["name"])
            self.assertEqual(stored.created_by, self.users[0]["id"])
            db.session.remove()

        search = self.client.get("/api/products?q=rolled", headers=auth)
        self.assertEqual(search.status_code, 200, search.get_json())
        self.assertEqual([item["id"] for item in search.get_json()["products"]], [product_id])

        detail = self.client.get(f"/api/products/{product_id}", headers=auth)
        self.assertEqual(detail.status_code, 200, detail.get_json())
        self.assertEqual(detail.get_json()["product"]["name"], values["name"])

        other_search = self.client.get("/api/products?q=rolled", headers=other_auth)
        self.assertEqual(other_search.status_code, 200)
        self.assertEqual(other_search.get_json()["products"], [])
        other_detail = self.client.get(
            f"/api/products/{product_id}", headers=other_auth
        )
        self.assertEqual(other_detail.status_code, 404)

        not_found = self.client.get("/api/products/99999999", headers=auth)
        self.assertEqual(not_found.status_code, 404)

        partial = self.client.post(
            "/api/products",
            json={
                "name": "Partial nutrition oats",
                "category": "grains_cereals",
                "energy_kj": 1500,
                "calories_kcal": 350,
            },
            headers=auth,
        )
        self.assertEqual(partial.status_code, 201, partial.get_json())
        partial_facts = partial.get_json()["product"]["nutrition_per_100g"]
        self.assertIsNone(partial_facts["protein_g"])
        self.assertIsNone(partial_facts["sodium_mg"])

    def test_barcode_lookup_and_ocr_import_sources(self):
        auth = {"Authorization": f"Bearer {self.tokens[0]}"}
        other_auth = {"Authorization": f"Bearer {self.tokens[1]}"}
        self.assertEqual(
            self.client.get(
                "/api/products/lookup/barcode/1234567890123"
            ).status_code,
            401,
        )
        provider_product = {
            "status": 1,
            "product": {
                "product_name": "Barcode test cereal",
                "brands": "Scan Foods",
                "serving_size": "30 g",
                "ingredients_text": "Whole grain oats, raisins",
                "image_url": "https://images.openfoodfacts.org/images/products/123/456/789/0123/front_en.3.400.jpg",
                "categories_tags": ["en:breakfast-cereals"],
                "ingredients_analysis_tags": ["en:vegan"],
                "nutriments": {
                    "energy-kj_100g": 1450,
                    "energy-kcal_100g": 350,
                    "carbohydrates_100g": 60,
                    "sugars_100g": 12,
                    "proteins_100g": 10,
                    "fat_100g": 5,
                    "saturated-fat_100g": 1,
                    "fiber_100g": 8,
                    "sodium_100g": 0.2,
                },
            },
        }

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self, _limit):
                return json.dumps(provider_product).encode()

        with patch("app.products.urlopen", return_value=FakeResponse()):
            lookup = self.client.get(
                "/api/products/lookup/barcode/1234567890123", headers=auth
            )
        self.assertEqual(lookup.status_code, 200, lookup.get_json())
        lookup_product = lookup.get_json()["product"]
        self.assertEqual(lookup_product["category"], "grains_cereals")
        self.assertEqual(lookup_product["dietary_tags"], ["vegan", "vegetarian"])
        self.assertEqual(lookup_product["sodium_mg"], 200)
        self.assertEqual(lookup_product["ingredients"], "Whole grain oats, raisins")
        self.assertEqual(
            lookup_product["image_url"],
            provider_product["product"]["image_url"],
        )
        self.assertIn("community data", lookup_product["source_label"])

        with patch("app.products.urlopen", return_value=FakeResponse()):
            imported = self.client.post(
                "/api/products/import/barcode",
                json={
                    "barcode": "1234567890123",
                    "category": "grains_cereals",
                    "reviewed_product": {
                        "name": "Reviewed breakfast cereal",
                        "brand": "My package says Scan Foods",
                        "ingredients": "Whole grain oats",
                        "calories_kcal": 351,
                    },
                },
                headers=auth,
            )
        self.assertEqual(imported.status_code, 201, imported.get_json())
        saved = imported.get_json()["product"]
        self.assertEqual(saved["source_type"], "open_food_facts")
        self.assertEqual(saved["barcode"], "1234567890123")
        self.assertEqual(saved["name"], "Reviewed breakfast cereal")
        self.assertEqual(saved["brand"], "My package says Scan Foods")
        self.assertEqual(saved["ingredients"], "Whole grain oats")
        self.assertEqual(saved["nutrition_per_100g"]["calories_kcal"], 351)
        self.assertEqual(saved["image_url"], provider_product["product"]["image_url"])
        self.assertIn("user-reviewed", saved["source_label"])
        self.assertEqual(saved["nutrition_per_serving"]["calories_kcal"], 105.3)
        duplicate = self.client.post(
            "/api/products/import/barcode",
            json={"barcode": "1234567890123", "category": "grains_cereals"},
            headers=auth,
        )
        self.assertEqual(duplicate.status_code, 200, duplicate.get_json())
        self.assertTrue(duplicate.get_json()["already_saved"])
        self.assertEqual(duplicate.get_json()["product"]["id"], saved["id"])
        with patch("app.products.urlopen", side_effect=AssertionError("unexpected provider call")):
            existing_lookup = self.client.get(
                "/api/products/lookup/barcode/1234567890123", headers=auth
            )
        self.assertEqual(existing_lookup.status_code, 200, existing_lookup.get_json())
        self.assertEqual(
            existing_lookup.get_json()["existing_product"]["id"],
            saved["id"],
        )
        self.assertEqual(
            self.client.get(
                f"/api/products/{saved['id']}", headers=other_auth
            ).status_code,
            404,
        )
        with patch("app.products.urlopen", return_value=FakeResponse()):
            other_owner_import = self.client.post(
                "/api/products/import/barcode",
                json={"barcode": "1234567890123", "category": "grains_cereals"},
                headers=other_auth,
            )
        self.assertEqual(other_owner_import.status_code, 201, other_owner_import.get_json())
        self.assertNotEqual(other_owner_import.get_json()["product"]["id"], saved["id"])

        ocr = self.client.post(
            "/api/products/import/ocr",
            json={
                "name": "OCR test cereal",
                "brand": None,
                "category": "grains_cereals",
                "barcode": "12345670",
                "ingredients": "Oats, seeds",
                "serving_size_g": 40,
                "calories_kcal": 320,
                "carbohydrates_g": 55,
                "sugars_g": 8,
                "protein_g": 12,
            },
            headers=auth,
        )
        self.assertEqual(ocr.status_code, 201, ocr.get_json())
        ocr_product = ocr.get_json()["product"]
        self.assertEqual(ocr_product["source_type"], "label_ocr")
        self.assertIsNone(ocr_product["brand"])
        self.assertEqual(ocr_product["ingredients"], "Oats, seeds")
        self.assertEqual(ocr_product["nutrition_per_serving"]["calories_kcal"], 128)

        invalid_serving = self.client.post(
            "/api/products/import/ocr",
            json={
                "name": "Invalid serving scan",
                "brand": None,
                "category": "grains_cereals",
                "serving_size_g": 0,
                "calories_kcal": 300,
            },
            headers=auth,
        )
        self.assertEqual(invalid_serving.status_code, 400)
        self.assertIn("Serving size", invalid_serving.get_json()["message"])
        suspicious_serving = self.client.post(
            "/api/products/import/ocr",
            json={
                "name": "Suspicious serving scan",
                "brand": None,
                "category": "grains_cereals",
                "serving_size_g": 0.5,
                "calories_kcal": 300,
            },
            headers=auth,
        )
        self.assertEqual(suspicious_serving.status_code, 400)
        confirmed_serving = self.client.post(
            "/api/products/import/ocr",
            json={
                "name": "Reviewed serving scan",
                "brand": None,
                "category": "grains_cereals",
                "serving_size_g": 0.5,
                "calories_kcal": 300,
                "review_confirmed": True,
            },
            headers=auth,
        )
        self.assertEqual(confirmed_serving.status_code, 201)

        invalid_barcode = self.client.get(
            "/api/products/lookup/barcode/invalid", headers=auth
        )
        self.assertEqual(invalid_barcode.status_code, 400)
        with patch(
            "app.products.urlopen",
            return_value=type(
                "Response",
                (),
                {
                    "__enter__": lambda self: self,
                    "__exit__": lambda self, *_args: False,
                    "read": lambda self, _limit: b'{"status":0}',
                },
            )(),
        ):
            missing_product = self.client.get(
                "/api/products/lookup/barcode/12345671", headers=auth
            )
        self.assertEqual(missing_product.status_code, 404)
        self.assertEqual(
            self.client.post(
                "/api/products/import/ocr",
                json={"name": "No facts", "category": "other"},
                headers=auth,
            ).status_code,
            400,
        )
        with patch("app.products.urlopen", side_effect=URLError("network unavailable")):
            network_failure = self.client.get(
                "/api/products/lookup/barcode/1111111111111", headers=auth
            )
        self.assertEqual(network_failure.status_code, 502)
        self.assertIn("Could not reach", network_failure.get_json()["message"])

        incomplete = {
            "status": 1,
            "product": {
                "product_name": "",
                "brands": "",
                "categories_tags": [],
                "nutriments": {},
            },
        }
        with patch(
            "app.products.urlopen",
            return_value=type(
                "IncompleteResponse",
                (),
                {
                    "__enter__": lambda self: self,
                    "__exit__": lambda self, *_args: False,
                    "read": lambda self, _limit: json.dumps(incomplete).encode(),
                },
            )(),
        ):
            incomplete_lookup = self.client.get(
                "/api/products/lookup/barcode/987654321098", headers=auth
            )
        self.assertEqual(incomplete_lookup.status_code, 200, incomplete_lookup.get_json())
        incomplete_product = incomplete_lookup.get_json()["product"]
        self.assertEqual(incomplete_product["name"], "")
        self.assertIsNone(incomplete_product["calories_kcal"])
        self.assertIsNone(incomplete_product["image_url"])
        self.assertIsNone(incomplete_product["serving_size_g"])

        with patch(
            "app.products.urlopen",
            return_value=type(
                "IncompleteResponse",
                (),
                {
                    "__enter__": lambda self: self,
                    "__exit__": lambda self, *_args: False,
                    "read": lambda self, _limit: json.dumps(incomplete).encode(),
                },
            )(),
        ):
            incomplete_import = self.client.post(
                "/api/products/import/barcode",
                json={
                    "barcode": "987654321098",
                    "reviewed_product": {
                        "name": "Name read from the package",
                        "category": "other",
                    },
                },
                headers=auth,
            )
        self.assertEqual(incomplete_import.status_code, 201, incomplete_import.get_json())
        missing_facts = incomplete_import.get_json()["product"]["nutrition_per_100g"]
        self.assertTrue(all(value is None for value in missing_facts.values()))

        with patch(
            "app.products._open_food_facts_product",
            return_value={
                "barcode": "1111111111111",
                "name": "Small serving package",
                "category": "other",
                "serving_size_g": 30,
                "calories_kcal": 300,
            },
        ):
            suspicious_import = self.client.post(
                "/api/products/import/barcode",
                json={
                    "barcode": "1111111111111",
                    "reviewed_product": {
                        "name": "Small serving package",
                        "category": "other",
                        "serving_size_g": 0.5,
                        "calories_kcal": 300,
                    },
                },
                headers=auth,
            )
        self.assertEqual(suspicious_import.status_code, 400)


if __name__ == "__main__":
    unittest.main(verbosity=2)
