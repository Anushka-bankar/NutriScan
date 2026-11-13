import sys
import unittest
import uuid
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402
from app.models import User  # noqa: E402


class MySQLAuthenticationIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.client = cls.app.test_client()
        cls.email = f"auth-test-{uuid.uuid4().hex}@example.test"
        cls.password = "Test-password-42"
        cls.user_id = None

    @classmethod
    def tearDownClass(cls):
        if cls.user_id is not None:
            with cls.app.app_context():
                user = db.session.get(User, cls.user_id)
                if user is not None:
                    db.session.delete(user)
                    db.session.commit()
                db.session.remove()

    def test_authentication_flow_against_mysql(self):
        health = self.client.get("/api/health/database")
        self.assertEqual(health.status_code, 200)
        self.assertEqual(health.get_json()["database"], "connected")

        unauthenticated = self.client.get("/api/auth/me")
        self.assertEqual(unauthenticated.status_code, 401)

        registration = self.client.post(
            "/api/auth/register",
            json={
                "full_name": "NutriScan Integration Test",
                "email": self.email,
                "password": self.password,
            },
        )
        self.assertEqual(registration.status_code, 201, registration.get_json())
        registered = registration.get_json()
        self.__class__.user_id = registered["user"]["id"]
        self.assertNotIn("password_hash", registered["user"])
        self.assertTrue(registered["token"])

        with self.app.app_context():
            saved_user = db.session.get(User, self.user_id)
            self.assertIsNotNone(saved_user)
            self.assertNotEqual(saved_user.password_hash, self.password)
            self.assertTrue(saved_user.password_hash.startswith("$2"))
            db.session.remove()

        duplicate = self.client.post(
            "/api/auth/register",
            json={
                "full_name": "Duplicate Test",
                "email": self.email.upper(),
                "password": self.password,
            },
        )
        self.assertEqual(duplicate.status_code, 409)

        login = self.client.post(
            "/api/auth/login",
            json={"email": self.email, "password": self.password},
        )
        self.assertEqual(login.status_code, 200, login.get_json())
        token = login.get_json()["token"]

        invalid_login = self.client.post(
            "/api/auth/login",
            json={"email": self.email, "password": "incorrect-password"},
        )
        self.assertEqual(invalid_login.status_code, 401)

        invalid_token = self.client.get(
            "/api/auth/me", headers={"Authorization": "Bearer invalid-token"}
        )
        self.assertEqual(invalid_token.status_code, 401)

        profile = self.client.get(
            "/api/auth/me", headers={"Authorization": f"Bearer {token}"}
        )
        self.assertEqual(profile.status_code, 200, profile.get_json())
        self.assertEqual(profile.get_json()["user"]["email"], self.email)

        print(
            "PASS: MySQL health, registration, bcrypt storage, duplicate rejection, "
            "login, invalid credentials, and protected route"
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
