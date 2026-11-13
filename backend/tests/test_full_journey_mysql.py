import sys
import unittest
import uuid
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402
from app.models import User  # noqa: E402


class FullNutriScanJourneyMySQLTest(unittest.TestCase):
    def test_registration_to_product_comparison_journey(self):
        app = create_app()
        client = app.test_client()
        email = f"journey-{uuid.uuid4().hex}@example.test"
        password = "Full-journey-password-42"
        user_id = None

        try:
            registration = client.post(
                "/api/auth/register",
                json={
                    "full_name": "Journey Test",
                    "email": email,
                    "password": password,
                },
            )
            self.assertEqual(registration.status_code, 201, registration.get_json())
            user_id = registration.get_json()["user"]["id"]

            login = client.post(
                "/api/auth/login",
                json={"email": email, "password": password},
            )
            self.assertEqual(login.status_code, 200, login.get_json())
            token = login.get_json()["token"]
            headers = {"Authorization": f"Bearer {token}"}

            profile = client.put(
                "/api/profile",
                headers=headers,
                json={
                    "age": 31,
                    "gender": "woman",
                    "height_cm": 168,
                    "weight_kg": 68,
                    "activity_level": "moderate",
                    "dietary_preferences": ["vegetarian"],
                    "health_goal": "lose_weight",
                },
            )
            self.assertEqual(profile.status_code, 200, profile.get_json())

            products = []
            for name, calories, sugar in (
                ("Journey product original", 370, 16),
                ("Journey product alternative", 310, 9),
            ):
                response = client.post(
                    "/api/products",
                    headers=headers,
                    json={
                        "name": name,
                        "brand": "Journey Test",
                        "category": "snacks",
                        "dietary_tags": ["vegetarian"],
                        "serving_size_g": 40,
                        "energy_kj": 1500,
                        "calories_kcal": calories,
                        "carbohydrates_g": 55,
                        "sugars_g": sugar,
                        "protein_g": 10,
                        "total_fat_g": 8,
                        "saturated_fat_g": 2,
                        "fibre_g": 7,
                        "sodium_mg": 180,
                    },
                )
                self.assertEqual(response.status_code, 201, response.get_json())
                products.append(response.get_json()["product"])

            detail = client.get(
                f"/api/products/{products[0]['id']}", headers=headers
            )
            self.assertEqual(detail.status_code, 200)

            recommendations = client.get(
                f"/api/products/{products[0]['id']}/recommendations",
                headers=headers,
            )
            self.assertEqual(recommendations.status_code, 200)
            self.assertEqual(
                recommendations.get_json()["recommendations"][0]["product"]["id"],
                products[1]["id"],
            )

            history = client.post(
                f"/api/products/{products[0]['id']}/history", headers=headers
            )
            self.assertEqual(history.status_code, 201)
            self.assertTrue(history.get_json()["history_entry"]["analyzed_at"])

            saved = client.post(
                f"/api/watchlist/{products[0]['id']}", headers=headers
            )
            self.assertEqual(saved.status_code, 201)
            watchlist = client.get("/api/watchlist", headers=headers)
            self.assertEqual(watchlist.status_code, 200)
            self.assertEqual(len(watchlist.get_json()["watchlist"]), 1)

            comparison = client.get(
                f"/api/products/compare?ids={products[0]['id']},{products[1]['id']}",
                headers=headers,
            )
            self.assertEqual(comparison.status_code, 200, comparison.get_json())
            self.assertEqual(len(comparison.get_json()["products"]), 2)

            print(
                "PASS: MySQL journey registration -> login -> profile -> product entry "
                "-> detail analysis -> recommendations -> history -> watchlist -> comparison"
            )
        finally:
            if user_id is not None:
                with app.app_context():
                    user = db.session.get(User, user_id)
                    if user is not None:
                        db.session.delete(user)
                        db.session.commit()
                    db.session.remove()


if __name__ == "__main__":
    unittest.main(verbosity=2)
