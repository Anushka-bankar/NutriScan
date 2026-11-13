import sys
import unittest
import uuid
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402
from app.health_profile import calculate_bmi, estimate_daily_calories  # noqa: E402
from app.models import User  # noqa: E402


class HealthProfileMySQLIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.client = cls.app.test_client()
        cls.users = []
        cls.tokens = []
        for index in range(2):
            email = f"profile-test-{uuid.uuid4().hex}@example.test"
            response = cls.client.post(
                "/api/auth/register",
                json={
                    "full_name": f"Profile Test {index}",
                    "email": email,
                    "password": "Profile-test-password-42",
                },
            )
            if response.status_code != 201:
                raise RuntimeError(f"Could not create integration test account: {response.get_json()}")
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

    def test_profile_create_update_persistence_and_ownership(self):
        auth = {"Authorization": f"Bearer {self.tokens[0]}"}
        other_auth = {"Authorization": f"Bearer {self.tokens[1]}"}

        missing_profile = self.client.get("/api/profile", headers=auth)
        self.assertEqual(missing_profile.status_code, 200)
        self.assertIsNone(missing_profile.get_json()["profile"])

        payload = {
            "age": 30,
            "gender": "woman",
            "height_cm": 170,
            "weight_kg": 65,
            "activity_level": "moderate",
            "dietary_preferences": ["vegetarian", "dairy_free"],
            "health_goal": "general_wellness",
        }
        created = self.client.put("/api/profile", json=payload, headers=auth)
        self.assertEqual(created.status_code, 200, created.get_json())
        profile = created.get_json()["profile"]
        self.assertEqual(profile["bmi"], {
            "value": 22.5,
            "category": "healthy",
            "label": "Healthy range",
        })
        self.assertEqual(profile["daily_calories"]["minimum"], 2172)
        self.assertEqual(profile["daily_calories"]["maximum"], 2430)

        other_user_profile = self.client.get("/api/profile", headers=other_auth)
        self.assertEqual(other_user_profile.status_code, 200)
        self.assertIsNone(other_user_profile.get_json()["profile"])

        updated_payload = {**payload, "weight_kg": 70, "health_goal": "build_muscle"}
        updated = self.client.put("/api/profile", json=updated_payload, headers=auth)
        self.assertEqual(updated.status_code, 200, updated.get_json())
        self.assertEqual(updated.get_json()["profile"]["weight_kg"], 70.0)
        self.assertEqual(updated.get_json()["profile"]["health_goal"], "build_muscle")

        persisted = self.client.get("/api/profile", headers=auth)
        self.assertEqual(persisted.status_code, 200)
        self.assertEqual(persisted.get_json()["profile"]["weight_kg"], 70.0)
        self.assertEqual(persisted.get_json()["profile"]["dietary_preferences"], [
            "dairy_free", "vegetarian"
        ])

        invalid = self.client.put(
            "/api/profile",
            json={**payload, "height_cm": 0},
            headers=auth,
        )
        self.assertEqual(invalid.status_code, 400)

        minor = self.client.put(
            "/api/profile",
            json={**payload, "age": 17},
            headers=auth,
        )
        self.assertEqual(minor.status_code, 200)
        minor_profile = minor.get_json()["profile"]
        self.assertEqual(minor_profile["bmi"]["category"], "not_classified")
        self.assertIsNone(minor_profile["daily_calories"])

        self.assertEqual(self.client.get("/api/profile").status_code, 401)

    def test_bmi_and_calorie_estimators(self):
        self.assertEqual(calculate_bmi(65, 170, 30)["value"], 22.5)
        self.assertEqual(calculate_bmi(65, 170, 17)["category"], "not_classified")
        self.assertIsNone(estimate_daily_calories(17, 170, 65, "moderate"))
        estimate = estimate_daily_calories(30, 170, 65, "moderate")
        self.assertEqual(estimate["minimum"], 2172)
        self.assertEqual(estimate["maximum"], 2430)


if __name__ == "__main__":
    unittest.main(verbosity=2)
