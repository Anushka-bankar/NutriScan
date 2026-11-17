import sys
import unittest
import uuid
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402
from app.models import HealthProfile, Product, ProductFoodClaimAnalysis, User  # noqa: E402


class FoodClaimsMySQLTests(unittest.TestCase):
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
                    "full_name": f"Claims Test {index}",
                    "email": f"claims-test-{uuid.uuid4().hex}@example.test",
                    "password": "Claims-test-password-42",
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

    def test_ocr_product_claim_history_persistence_and_deletion_snapshot(self):
        auth = {"Authorization": f"Bearer {self.tokens[0]}"}
        other_auth = {"Authorization": f"Bearer {self.tokens[1]}"}
        invalid_source = self.client.post(
            "/api/products",
            json={
                "name": "Manual product",
                "category": "grains_cereals",
                "ingredients": "wheat",
                "packaging_text": "Sugar Free",
                "calories_kcal": 300,
            },
            headers=auth,
        )
        self.assertEqual(invalid_source.status_code, 400, invalid_source.get_json())
        created = self.client.post(
            "/api/products/import/ocr",
            json={
                "name": "Claims test cereal",
                "category": "grains_cereals",
                "ingredients": "Whole wheat, sugar",
                "packaging_text": "Sugar Free; high protein",
                "sugars_g": 0.2,
                "protein_g": 11,
                "calories_kcal": 300,
            },
            headers=auth,
        )
        self.assertEqual(created.status_code, 201, created.get_json())
        product_id = created.get_json()["product"]["id"]
        product_detail = self.client.get(
            f"/api/products/{created.get_json()['product']['id']}",
            headers=auth,
        )
        self.assertEqual(product_detail.status_code, 200)
        self.assertEqual(
            product_detail.get_json()["product"]["packaging_text"],
            "Sugar Free; high protein",
        )

        with self.app.app_context():
            db.session.add(
                HealthProfile(
                    user_id=self.users[0]["id"],
                    dietary_preferences=["gluten_free"],
                    health_goal="general_wellness",
                )
            )
            db.session.commit()
            db.session.remove()

        endpoint = f"/api/products/{product_id}/claims/analyze"
        self.assertEqual(self.client.post(endpoint, json={}).status_code, 401)
        response = self.client.post(endpoint, json={}, headers=auth)
        self.assertEqual(response.status_code, 201, response.get_json())
        analysis = response.get_json()["analysis"]
        self.assertEqual(analysis["input_source"], "ocr")
        self.assertEqual(analysis["claims"][0]["status"], "supported")
        self.assertEqual(analysis["product_snapshot"]["name"], "Claims test cereal")
        self.assertTrue(analysis["analyzed_at"])

        edited = self.client.post(
            endpoint,
            json={"claim_text": "Sugar Free; Vegan; mystery miracle"},
            headers=auth,
        )
        self.assertEqual(edited.status_code, 201, edited.get_json())
        self.assertEqual(edited.get_json()["analysis"]["input_source"], "manual_or_edited")
        self.assertEqual(
            [claim["code"] for claim in edited.get_json()["analysis"]["claims"]],
            ["sugar_free", "vegan", "unrecognized_claim"],
        )

        for body in (
            {"claim_text": ""},
            {"claim_text": 42},
            {"claim_text": "x" * 20001},
        ):
            with self.subTest(body=type(body.get("claim_text")).__name__):
                invalid = self.client.post(endpoint, json=body, headers=auth)
                self.assertEqual(invalid.status_code, 400, invalid.get_json())

        history = self.client.get(
            "/api/products/claims/history", headers=auth
        )
        self.assertEqual(history.status_code, 200, history.get_json())
        self.assertEqual(len(history.get_json()["history"]), 2)
        filtered = self.client.get(
            f"/api/products/claims/history?product_id={product_id}",
            headers=auth,
        )
        self.assertEqual(len(filtered.get_json()["history"]), 2)
        self.assertEqual(
            self.client.get("/api/products/claims/history").status_code,
            401,
        )
        self.assertEqual(
            self.client.get(
                "/api/products/claims/history", headers=other_auth
            ).get_json()["history"],
            [],
        )
        self.assertEqual(
            self.client.post(endpoint, json={}, headers=other_auth).status_code,
            404,
        )
        self.assertEqual(
            self.client.get(
                f"/api/products/claims/history?product_id=bad", headers=auth
            ).status_code,
            400,
        )

        with self.app.app_context():
            saved = db.session.get(ProductFoodClaimAnalysis, analysis["id"])
            self.assertIsNotNone(saved)
            self.assertEqual(saved.user_id, self.users[0]["id"])
            self.assertEqual(saved.product_id, product_id)
            self.assertEqual(saved.product_identity_snapshot, product_id)
            self.assertEqual(saved.product_snapshot["ingredients"], "Whole wheat, sugar")
            product = db.session.get(Product, product_id)
            product.name = "Changed cereal name"
            db.session.commit()
            db.session.delete(product)
            db.session.commit()
            db.session.refresh(saved)
            self.assertIsNone(saved.product_id)
            self.assertEqual(saved.product_name_snapshot, "Claims test cereal")
            db.session.remove()

        preserved = self.client.get(
            "/api/products/claims/history", headers=auth
        ).get_json()["history"]
        preserved_entry = next(item for item in preserved if item["id"] == analysis["id"])
        self.assertIsNone(preserved_entry["product_id"])
        self.assertEqual(preserved_entry["product_identity_snapshot"], product_id)
        self.assertEqual(preserved_entry["product_snapshot"]["name"], "Claims test cereal")


if __name__ == "__main__":
    unittest.main(verbosity=2)
