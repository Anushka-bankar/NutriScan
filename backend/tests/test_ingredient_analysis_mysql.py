import sys
import unittest
import uuid
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402
from app.models import HealthProfile, Product, ProductIngredientAnalysis, User  # noqa: E402


class IngredientAnalysisMySQLTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.client = cls.app.test_client()
        cls.users = []
        cls.tokens = []
        for index in range(2):
            response = cls.client.post(
                "/api/auth/register",
                json={
                    "full_name": f"Ingredient Test {index}",
                    "email": f"ingredient-test-{uuid.uuid4().hex}@example.test",
                    "password": "Ingredient-test-password-42",
                },
            )
            if response.status_code != 201:
                raise RuntimeError(
                    f"Could not create integration account: {response.get_json()}"
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

    def test_analysis_persistence_personalization_and_owner_isolation(self):
        auth = {"Authorization": f"Bearer {self.tokens[0]}"}
        other_auth = {"Authorization": f"Bearer {self.tokens[1]}"}
        created = self.client.post(
            "/api/products",
            json={
                "name": "Ingredient analysis cereal",
                "category": "grains_cereals",
                "ingredients": (
                    "Sugar, soy lecithin, milk powder, wheat flour, gelatin, "
                    "unknown extract"
                ),
                "calories_kcal": 300,
            },
            headers=auth,
        )
        self.assertEqual(created.status_code, 201, created.get_json())
        product_id = created.get_json()["product"]["id"]

        with self.app.app_context():
            db.session.add(
                HealthProfile(
                    user_id=self.users[0]["id"],
                    dietary_preferences=["vegan", "dairy_free", "gluten_free"],
                    health_goal="manage_condition",
                )
            )
            db.session.commit()
            db.session.remove()

        self.assertEqual(
            self.client.get(
                f"/api/products/{product_id}/ingredients/latest"
            ).status_code,
            401,
        )
        latest_before = self.client.get(
            f"/api/products/{product_id}/ingredients/latest",
            headers=auth,
        )
        self.assertEqual(latest_before.status_code, 200, latest_before.get_json())
        self.assertIsNone(latest_before.get_json()["analysis"])

        analyzed = self.client.post(
            f"/api/products/{product_id}/ingredients/analyze",
            json={},
            headers=auth,
        )
        self.assertEqual(analyzed.status_code, 201, analyzed.get_json())
        result = analyzed.get_json()["analysis"]
        self.assertEqual(len(result["entries"]), 6)
        self.assertEqual(result["summary"]["unmatched_count"], 1)
        self.assertEqual(result["summary"]["dietary_conflict_count"], 4)
        self.assertIn("condition-management goal", result["summary"]["health_goal_context"])
        self.assertTrue(result["analyzed_at"])
        self.assertEqual(result["ingredients_text"], created.get_json()["product"]["ingredients"])

        stored_result = self.client.get(
            f"/api/products/{product_id}/ingredients/latest",
            headers=auth,
        )
        self.assertEqual(stored_result.status_code, 200, stored_result.get_json())
        self.assertEqual(
            stored_result.get_json()["analysis"]["id"],
            result["id"],
        )

        for invalid in ("", "  ", 17, "x" * 10001):
            with self.subTest(value=type(invalid).__name__):
                response = self.client.post(
                    f"/api/products/{product_id}/ingredients/analyze",
                    json={"ingredients": invalid},
                    headers=auth,
                )
                self.assertEqual(response.status_code, 400, response.get_json())

        other_detail = self.client.get(
            f"/api/products/{product_id}/ingredients/latest",
            headers=other_auth,
        )
        self.assertEqual(other_detail.status_code, 404)
        other_analysis = self.client.post(
            f"/api/products/{product_id}/ingredients/analyze",
            json={"ingredients": "sugar"},
            headers=other_auth,
        )
        self.assertEqual(other_analysis.status_code, 404)
        other_product = self.client.post(
            "/api/products",
            json={
                "name": "Ingredient product without profile",
                "category": "other",
                "ingredients": "mystery extract",
                "calories_kcal": 10,
            },
            headers=other_auth,
        )
        self.assertEqual(other_product.status_code, 201, other_product.get_json())
        no_profile_analysis = self.client.post(
            f"/api/products/{other_product.get_json()['product']['id']}/ingredients/analyze",
            json={},
            headers=other_auth,
        )
        self.assertEqual(no_profile_analysis.status_code, 201)
        self.assertEqual(
            no_profile_analysis.get_json()["analysis"]["summary"]["dietary_preferences"],
            [],
        )

        edited = self.client.post(
            f"/api/products/{product_id}/ingredients/analyze",
            json={"ingredients": "Aspartame, may contain milk"},
            headers=auth,
        )
        self.assertEqual(edited.status_code, 201, edited.get_json())
        self.assertEqual(
            edited.get_json()["analysis"]["ingredients_text"],
            "Aspartame, may contain milk",
        )
        self.assertIn(
            "phenylketonuria (PKU)",
            edited.get_json()["analysis"]["entries"][0]["health_considerations"],
        )

        with self.app.app_context():
            persisted = db.session.get(ProductIngredientAnalysis, result["id"])
            self.assertIsNotNone(persisted)
            self.assertEqual(persisted.user_id, self.users[0]["id"])
            self.assertEqual(persisted.product_id, product_id)
            self.assertEqual(persisted.ingredients_text, result["ingredients_text"])

            product = db.session.get(Product, product_id)
            db.session.delete(product)
            db.session.commit()
            db.session.refresh(persisted)
            self.assertIsNone(persisted.product_id)
            self.assertEqual(persisted.product_name_snapshot, "Ingredient analysis cereal")
            db.session.remove()

    def test_historical_comparison_validation_isolation_and_deleted_product(self):
        auth = {"Authorization": f"Bearer {self.tokens[0]}"}
        other_auth = {"Authorization": f"Bearer {self.tokens[1]}"}
        product_response = self.client.post(
            "/api/products",
            json={
                "name": "Historical ingredient comparison",
                "category": "snacks",
                "ingredients": "Sugar, salt, corn starch",
                "calories_kcal": 300,
            },
            headers=auth,
        )
        self.assertEqual(product_response.status_code, 201, product_response.get_json())
        product_id = product_response.get_json()["product"]["id"]

        older_response = self.client.post(
            f"/api/products/{product_id}/ingredients/analyze",
            json={"ingredients": "Sugar, salt, corn starch"},
            headers=auth,
        )
        newer_response = self.client.post(
            f"/api/products/{product_id}/ingredients/analyze",
            json={"ingredients": "salt; SUGAR; glucose"},
            headers=auth,
        )
        self.assertEqual(older_response.status_code, 201, older_response.get_json())
        self.assertEqual(newer_response.status_code, 201, newer_response.get_json())
        older_id = older_response.get_json()["analysis"]["id"]
        newer_id = newer_response.get_json()["analysis"]["id"]

        comparison_url = "/api/products/ingredients/compare"
        comparison = self.client.post(
            comparison_url,
            json={"older_analysis_id": older_id, "newer_analysis_id": newer_id},
            headers=auth,
        )
        self.assertEqual(comparison.status_code, 200, comparison.get_json())
        result = comparison.get_json()
        self.assertEqual([item["name"] for item in result["added"]], ["glucose"])
        self.assertEqual(
            [item["name"] for item in result["removed"]], ["corn starch"]
        )
        self.assertEqual(len(result["unchanged"]), 2)
        self.assertEqual(len(result["order_changes"]), 1)
        self.assertEqual(result["older"]["product_id"], product_id)
        self.assertEqual(result["newer"]["product_id"], product_id)
        self.assertEqual(
            result["older"]["ingredients_text"], "Sugar, salt, corn starch"
        )

        history = self.client.get(
            "/api/products/ingredients/history", headers=auth
        )
        self.assertEqual(history.status_code, 200, history.get_json())
        self.assertTrue(
            {older_id, newer_id}.issubset(
                {entry["id"] for entry in history.get_json()["history"]}
            )
        )
        self.assertEqual(
            self.client.get("/api/products/ingredients/history").status_code, 401
        )

        for invalid_body in (
            {"older_analysis_id": True, "newer_analysis_id": newer_id},
            {"older_analysis_id": older_id, "newer_analysis_id": older_id},
            {"older_analysis_id": -1, "newer_analysis_id": newer_id},
        ):
            with self.subTest(body=invalid_body):
                response = self.client.post(
                    comparison_url, json=invalid_body, headers=auth
                )
                self.assertEqual(response.status_code, 400, response.get_json())

        not_found = self.client.post(
            comparison_url,
            json={
                "older_analysis_id": older_id,
                "newer_analysis_id": 2147483647,
            },
            headers=auth,
        )
        self.assertEqual(not_found.status_code, 404, not_found.get_json())

        reversed_order = self.client.post(
            comparison_url,
            json={
                "older_analysis_id": newer_id,
                "newer_analysis_id": older_id,
            },
            headers=auth,
        )
        self.assertEqual(
            reversed_order.status_code, 400, reversed_order.get_json()
        )

        other_product_response = self.client.post(
            "/api/products",
            json={
                "name": "Unrelated ingredient product",
                "category": "snacks",
                "ingredients": "Salt",
                "calories_kcal": 100,
            },
            headers=auth,
        )
        self.assertEqual(other_product_response.status_code, 201)
        unrelated_analysis = self.client.post(
            f"/api/products/{other_product_response.get_json()['product']['id']}/ingredients/analyze",
            json={"ingredients": "salt"},
            headers=auth,
        )
        self.assertEqual(unrelated_analysis.status_code, 201)
        cross_product = self.client.post(
            comparison_url,
            json={
                "older_analysis_id": older_id,
                "newer_analysis_id": unrelated_analysis.get_json()["analysis"]["id"],
            },
            headers=auth,
        )
        self.assertEqual(cross_product.status_code, 400, cross_product.get_json())

        other_product_response = self.client.post(
            "/api/products",
            json={
                "name": "Other user's ingredient product",
                "category": "snacks",
                "ingredients": "Sugar",
                "calories_kcal": 100,
            },
            headers=other_auth,
        )
        self.assertEqual(other_product_response.status_code, 201)
        other_analysis = self.client.post(
            f"/api/products/{other_product_response.get_json()['product']['id']}/ingredients/analyze",
            json={"ingredients": "sugar"},
            headers=other_auth,
        )
        self.assertEqual(other_analysis.status_code, 201)
        cross_user = self.client.post(
            comparison_url,
            json={
                "older_analysis_id": older_id,
                "newer_analysis_id": other_analysis.get_json()["analysis"]["id"],
            },
            headers=auth,
        )
        self.assertEqual(cross_user.status_code, 404, cross_user.get_json())

        with self.app.app_context():
            product = db.session.get(Product, product_id)
            product.name = "Edited product name"
            db.session.commit()
            persisted_snapshot = db.session.get(ProductIngredientAnalysis, older_id)
            self.assertEqual(
                persisted_snapshot.product_name_snapshot,
                "Historical ingredient comparison",
            )
            db.session.delete(product)
            db.session.commit()
            db.session.remove()

        deleted_product_comparison = self.client.post(
            comparison_url,
            json={"older_analysis_id": older_id, "newer_analysis_id": newer_id},
            headers=auth,
        )
        self.assertEqual(
            deleted_product_comparison.status_code,
            200,
            deleted_product_comparison.get_json(),
        )
        deleted_result = deleted_product_comparison.get_json()
        self.assertIsNone(deleted_result["older"]["product_id"])
        self.assertEqual(
            deleted_result["older"]["product_identity_snapshot"], product_id
        )
        self.assertEqual(
            deleted_result["newer"]["product_identity_snapshot"], product_id
        )
        self.assertFalse(deleted_result["older"]["product_available"])
        self.assertEqual(
            deleted_result["older"]["product_name"],
            "Historical ingredient comparison",
        )
        self.assertEqual(
            deleted_result["older"]["ingredients_text"], "Sugar, salt, corn starch"
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
