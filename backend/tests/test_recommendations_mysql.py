import sys
import unittest
import uuid
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402
from app.models import HealthProfile, Product, ProductAnalysisHistory, ProductWatchlist, User  # noqa: E402


class ProductRecommendationMySQLTests(unittest.TestCase):
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
                    "full_name": f"Recommendation Test {index}",
                    "email": f"recommend-test-{uuid.uuid4().hex}@example.test",
                    "password": "Recommend-test-password-42",
                },
            )
            if response.status_code != 201:
                raise RuntimeError(f"Could not create test user: {response.get_json()}")
            data = response.get_json()
            cls.users.append(data["user"])
            cls.tokens.append(data["token"])

        with cls.app.app_context():
            for user_data in cls.users:
                db.session.add(
                    HealthProfile(
                        user_id=user_data["id"],
                        age=30,
                        height_cm=170,
                        weight_kg=70,
                        activity_level="moderate",
                        dietary_preferences=["vegan"],
                        health_goal="lose_weight",
                    )
                )
            db.session.commit()
            cls.product_ids = {}
            cls.product_ids["target"] = cls._add_product(
                cls.users[0]["id"],
                "Target oat snack",
                "snacks",
                ["vegan"],
                calories=360,
                sugar=18,
                protein=6,
                saturated_fat=4,
                sodium=100,
                fibre=3,
            )
            cls.product_ids["match"] = cls._add_product(
                cls.users[0]["id"],
                "Lower calorie oat snack",
                "snacks",
                ["vegan"],
                calories=300,
                sugar=10,
                protein=8,
                saturated_fat=2,
                sodium=None,
                fibre=5,
            )
            cls.product_ids["missing_primary"] = cls._add_product(
                cls.users[0]["id"],
                "Snack without calories",
                "snacks",
                ["vegan"],
                calories=None,
                sugar=5,
                protein=8,
                saturated_fat=2,
                sodium=50,
                fibre=5,
            )
            cls.product_ids["wrong_diet"] = cls._add_product(
                cls.users[0]["id"],
                "Non-vegan snack",
                "snacks",
                ["vegetarian"],
                calories=250,
                sugar=5,
                protein=8,
                saturated_fat=2,
                sodium=50,
                fibre=5,
            )
            cls.product_ids["wrong_category"] = cls._add_product(
                cls.users[0]["id"],
                "Low calorie beverage",
                "beverages",
                ["vegan"],
                calories=1,
                sugar=0,
                protein=0,
                saturated_fat=0,
                sodium=0,
                fibre=0,
            )
            cls.product_ids["other_owner"] = cls._add_product(
                cls.users[1]["id"],
                "Other user's vegan snack",
                "snacks",
                ["vegan"],
                calories=100,
                sugar=1,
                protein=20,
                saturated_fat=0,
                sodium=1,
                fibre=10,
            )
            db.session.commit()

    @classmethod
    def _add_product(
        cls,
        user_id,
        name,
        category,
        tags,
        calories,
        sugar,
        protein,
        saturated_fat,
        sodium,
        fibre,
    ):
        product = Product(
            created_by=user_id,
            name=name,
            category=category,
            dietary_tags=tags,
            energy_kj=1500,
            calories_kcal=calories,
            carbohydrates_g=40,
            sugars_g=sugar,
            protein_g=protein,
            total_fat_g=8,
            saturated_fat_g=saturated_fat,
            fibre_g=fibre,
            sodium_mg=sodium,
            source_type="user_entered",
            source_label="User-entered; not independently verified",
        )
        db.session.add(product)
        db.session.flush()
        return product.id

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            for user_data in cls.users:
                user = db.session.get(User, user_data["id"])
                if user is not None:
                    db.session.delete(user)
            db.session.commit()
            db.session.remove()

    def test_goal_category_diet_missing_data_and_owner_filters(self):
        auth = {"Authorization": f"Bearer {self.tokens[0]}"}
        response = self.client.get(
            f"/api/products/{self.product_ids['target']}/recommendations",
            headers=auth,
        )
        self.assertEqual(response.status_code, 200, response.get_json())
        payload = response.get_json()
        recommended_ids = [
            item["product"]["id"] for item in payload["recommendations"]
        ]
        self.assertEqual(recommended_ids, [self.product_ids["match"]])

        recommendation = payload["recommendations"][0]
        self.assertTrue(any("Calories per 100 g decreases" in reason for reason in recommendation["reasons"]))
        comparison = {
            item["field"]: item for item in recommendation["comparisons"]
        }
        self.assertFalse(comparison["sodium_mg"]["available"])
        self.assertIsNone(comparison["sodium_mg"]["alternative_value"])
        self.assertIsNone(comparison["sodium_mg"]["difference"])
        self.assertTrue(comparison["calories_kcal"]["goal_improvement"])
        self.assertEqual(
            recommendation["product"]["source_label"],
            "User-entered; not independently verified",
        )

        changed_category = self.client.patch(
            f"/api/products/{self.product_ids['target']}/classification",
            json={"category": "bakery", "dietary_tags": ["vegan"]},
            headers=auth,
        )
        self.assertEqual(changed_category.status_code, 200)
        no_alternative = self.client.get(
            f"/api/products/{self.product_ids['target']}/recommendations",
            headers=auth,
        )
        self.assertEqual(no_alternative.status_code, 200)
        self.assertEqual(no_alternative.get_json()["recommendations"], [])
        self.assertIn("No suitable alternative", no_alternative.get_json()["message"])
        restored_category = self.client.patch(
            f"/api/products/{self.product_ids['target']}/classification",
            json={"category": "snacks", "dietary_tags": ["vegan"]},
            headers=auth,
        )
        self.assertEqual(restored_category.status_code, 200)

        other_owner = self.client.get(
            f"/api/products/{self.product_ids['other_owner']}/recommendations",
            headers=auth,
        )
        self.assertEqual(other_owner.status_code, 404)

    def test_goal_change_and_no_matching_candidate(self):
        auth = {"Authorization": f"Bearer {self.tokens[0]}"}
        with self.app.app_context():
            profile = db.session.get(HealthProfile, self.users[0]["id"])
            profile.health_goal = "build_muscle"
            db.session.commit()

        response = self.client.get(
            f"/api/products/{self.product_ids['target']}/recommendations",
            headers=auth,
        )
        self.assertEqual(response.status_code, 200)
        recommendations = response.get_json()["recommendations"]
        ids = [item["product"]["id"] for item in recommendations]
        self.assertIn(self.product_ids["match"], ids)
        self.assertNotIn(self.product_ids["wrong_diet"], ids)
        self.assertNotIn(self.product_ids["wrong_category"], ids)
        self.assertTrue(
            all("muscle-building" in item["goal_label"] for item in recommendations)
        )
        without_calories = next(
            item for item in recommendations
            if item["product"]["id"] == self.product_ids["missing_primary"]
        )
        comparison = {
            item["field"]: item for item in without_calories["comparisons"]
        }
        self.assertFalse(comparison["calories_kcal"]["available"])
        self.assertEqual(comparison["calories_kcal"]["target_value"], 360)
        self.assertIsNone(comparison["calories_kcal"]["alternative_value"])

        with self.app.app_context():
            profile = db.session.get(HealthProfile, self.users[0]["id"])
            profile.health_goal = "manage_condition"
            db.session.commit()
        no_match = self.client.get(
            f"/api/products/{self.product_ids['target']}/recommendations",
            headers=auth,
        )
        self.assertEqual(no_match.status_code, 200)
        self.assertEqual(no_match.get_json()["recommendations"], [])
        self.assertIn("does not make condition-specific", no_match.get_json()["message"])

    def test_classification_endpoint_owner_and_validation(self):
        auth = {"Authorization": f"Bearer {self.tokens[0]}"}
        other_auth = {"Authorization": f"Bearer {self.tokens[1]}"}
        response = self.client.patch(
            f"/api/products/{self.product_ids['target']}/classification",
            json={"category": ["snacks"], "dietary_tags": []},
            headers=auth,
        )
        self.assertEqual(response.status_code, 400)
        response = self.client.patch(
            f"/api/products/{self.product_ids['target']}/classification",
            json={"category": "snacks", "dietary_tags": ["vegan"]},
            headers=auth,
        )
        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertEqual(response.get_json()["product"]["category"], "snacks")
        response = self.client.patch(
            f"/api/products/{self.product_ids['target']}/classification",
            json={"category": "snacks", "dietary_tags": ["vegan"]},
            headers=other_auth,
        )
        self.assertEqual(response.status_code, 404)

    def test_analysis_history_watchlist_and_product_deletion_snapshots(self):
        auth = {"Authorization": f"Bearer {self.tokens[0]}"}
        other_auth = {"Authorization": f"Bearer {self.tokens[1]}"}
        self.assertEqual(self.client.get("/api/history").status_code, 401)
        self.assertEqual(self.client.get("/api/watchlist").status_code, 401)
        product = Product(
            created_by=self.users[0]["id"],
            name="History lifecycle product",
            category="snacks",
            dietary_tags=["vegan"],
            calories_kcal=240,
            energy_kj=1000,
            carbohydrates_g=30,
            sugars_g=5,
            protein_g=10,
            total_fat_g=6,
            saturated_fat_g=1,
            fibre_g=4,
            sodium_mg=30,
            source_type="user_entered",
            source_label="User-entered; not independently verified",
        )
        with self.app.app_context():
            db.session.add(product)
            db.session.commit()
            product_id = product.id

        first_analysis = self.client.post(
            f"/api/products/{product_id}/history", headers=auth
        )
        second_analysis = self.client.post(
            f"/api/products/{product_id}/history", headers=auth
        )
        self.assertEqual(first_analysis.status_code, 201)
        self.assertEqual(second_analysis.status_code, 201)
        first_time = first_analysis.get_json()["history_entry"]["analyzed_at"]
        history = self.client.get(
            "/api/history?category=snacks&order=oldest", headers=auth
        )
        self.assertEqual(history.status_code, 200)
        self.assertEqual(len(history.get_json()["history"]), 2)
        self.assertEqual(
            history.get_json()["history"][0]["analyzed_at"], first_time
        )

        added = self.client.post(f"/api/watchlist/{product_id}", headers=auth)
        duplicate = self.client.post(f"/api/watchlist/{product_id}", headers=auth)
        self.assertEqual(added.status_code, 201)
        self.assertEqual(duplicate.status_code, 200)
        self.assertEqual(
            added.get_json()["watchlist_entry"]["id"],
            duplicate.get_json()["watchlist_entry"]["id"],
        )
        watchlist = self.client.get("/api/watchlist?q=lifecycle", headers=auth)
        self.assertEqual(len(watchlist.get_json()["watchlist"]), 1)

        other_watchlist = self.client.get(
            "/api/watchlist", headers={"Authorization": f"Bearer {self.tokens[1]}"}
        )
        self.assertEqual(other_watchlist.status_code, 200)
        self.assertEqual(other_watchlist.get_json()["watchlist"], [])
        other_history = self.client.get(
            "/api/history", headers=other_auth
        )
        self.assertEqual(other_history.get_json()["history"], [])
        foreign_add = self.client.post(
            f"/api/watchlist/{product_id}", headers=other_auth
        )
        self.assertEqual(foreign_add.status_code, 404)
        foreign_remove = self.client.delete(
            f"/api/watchlist/entries/{added.get_json()['watchlist_entry']['id']}",
            headers=other_auth,
        )
        self.assertEqual(foreign_remove.status_code, 404)

        changed = self.client.patch(
            f"/api/products/{product_id}/classification",
            json={"category": "bakery", "dietary_tags": ["vegan"]},
            headers=auth,
        )
        self.assertEqual(changed.status_code, 200)
        prior_history = self.client.get("/api/history", headers=auth).get_json()["history"]
        self.assertTrue(all(entry["product"]["category"] == "snacks" for entry in prior_history))

        comparison = self.client.get(
            f"/api/products/compare?ids={product_id},{self.product_ids['target']}",
            headers=auth,
        )
        self.assertEqual(comparison.status_code, 200)
        self.assertEqual(len(comparison.get_json()["products"]), 2)

        deleted = self.client.delete(f"/api/products/{product_id}", headers=auth)
        self.assertEqual(deleted.status_code, 200)
        preserved_history = self.client.get("/api/history", headers=auth).get_json()["history"]
        retained = [
            item for item in preserved_history
            if item["product"]["name"] == "History lifecycle product"
        ]
        self.assertEqual(len(retained), 2)
        self.assertTrue(all(not item["product_available"] for item in retained))
        self.assertTrue(all(item["product"]["category"] == "snacks" for item in retained))

        retained_watchlist = self.client.get("/api/watchlist", headers=auth).get_json()["watchlist"]
        self.assertEqual(len(retained_watchlist), 1)
        self.assertFalse(retained_watchlist[0]["product_available"])
        self.assertEqual(retained_watchlist[0]["product"]["category"], "snacks")
        remove = self.client.delete(
            f"/api/watchlist/entries/{added.get_json()['watchlist_entry']['id']}",
            headers=auth,
        )
        self.assertEqual(remove.status_code, 200)
        self.assertEqual(self.client.get("/api/watchlist", headers=auth).get_json()["watchlist"], [])

        with self.app.app_context():
            self.assertEqual(
                db.session.query(ProductAnalysisHistory)
                .filter_by(user_id=self.users[0]["id"])
                .count(),
                2,
            )
            self.assertEqual(
                db.session.query(ProductWatchlist)
                .filter_by(user_id=self.users[0]["id"])
                .count(),
                0,
            )
            db.session.remove()


if __name__ == "__main__":
    unittest.main(verbosity=2)
