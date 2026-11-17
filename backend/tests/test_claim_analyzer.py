import unittest
from types import SimpleNamespace

from app.claim_analyzer import analyze_food_claims, detect_food_claims


def product(**overrides):
    values = {
        "category": "snacks",
        "ingredients": "Whole grain, salt",
        "sugars_g": 0.4,
        "total_fat_g": 2.5,
        "protein_g": 12,
        "fibre_g": 6,
        "sodium_mg": 250,
        "carbohydrates_g": 30,
        "source_label": "User-entered; not independently verified",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


class FoodClaimAnalyzerTests(unittest.TestCase):
    def test_detects_supported_nutrition_dietary_and_marketing_claims(self):
        claims = detect_food_claims(
            "No Added Sugar, Sugar Free; Low Sugar\nHigh Protein; Source of Protein; "
            "Low Fat; Fat Free; Zero Cholesterol; High Fibre; Organic; Natural; "
            "Gluten Free; Vegan; Clinically Proven"
        )
        self.assertEqual(
            {claim["code"] for claim in claims},
            {
                "no_added_sugar",
                "sugar_free",
                "low_sugar",
                "high_protein",
                "source_of_protein",
                "low_fat",
                "fat_free",
                "zero_cholesterol",
                "high_fibre",
                "organic",
                "natural",
                "gluten_free",
                "vegan",
                "clinically_proven",
            },
        )

    def test_mass_claims_use_saved_per_100g_values_and_solid_category(self):
        results = analyze_food_claims("Sugar Free; Low Fat", product())["claims"]
        self.assertEqual([claim["status"] for claim in results], ["supported", "supported"])
        self.assertIn("per 100 g", results[0]["explanation"])
        above_threshold = analyze_food_claims(
            "Sugar Free", product(sugars_g=0.51)
        )["claims"][0]
        self.assertEqual(above_threshold["status"], "potentially_inconsistent")

    def test_missing_values_and_inapplicable_bases_remain_unverifiable(self):
        missing = analyze_food_claims(
            "Sugar Free", product(sugars_g=None)
        )["claims"][0]
        self.assertEqual(missing["status"], "unverifiable")
        self.assertIsNone(missing["evidence"][0]["value"])

        beverage = analyze_food_claims(
            "Sugar Free", product(category="beverages", sugars_g=0.1)
        )["claims"][0]
        self.assertEqual(beverage["status"], "unverifiable")
        self.assertIn("per 100 ml", beverage["explanation"])

        unclear = analyze_food_claims(
            "Low Fat", product(category="other", total_fat_g=0.1)
        )["claims"][0]
        self.assertEqual(unclear["status"], "unverifiable")

    def test_unimplemented_nutrition_criteria_show_available_values_and_correct_units(self):
        claim = analyze_food_claims("Low Sodium", product())["claims"][0]
        self.assertEqual(claim["status"], "unverifiable")
        self.assertEqual(claim["evidence"][0]["value"], 250)
        self.assertEqual(claim["evidence"][0]["unit"], "mg")

        cholesterol = analyze_food_claims("Zero Cholesterol", product())["claims"][0]
        self.assertEqual(cholesterol["status"], "unverifiable")
        self.assertIsNone(cholesterol["evidence"][0]["value"])
        self.assertEqual(cholesterol["evidence"][0]["unit"], "mg")

    def test_ingredient_evidence_is_cautious_and_preserves_unknown_claims(self):
        results = analyze_food_claims(
            "No Added Sugar; Gluten Free; no preservatives; miracle metabolism",
            product(ingredients="Sugar, wheat flour, sodium benzoate"),
            manual_input=True,
        )["claims"]
        by_code = {claim["code"]: claim for claim in results}
        self.assertEqual(by_code["no_added_sugar"]["status"], "potentially_inconsistent")
        self.assertEqual(by_code["gluten_free"]["status"], "potentially_inconsistent")
        self.assertEqual(by_code["no_preservatives"]["status"], "potentially_inconsistent")
        self.assertEqual(by_code["unrecognized_claim"]["status"], "unverifiable")
        self.assertIn("not a legal finding", by_code["no_preservatives"]["explanation"])

    def test_personal_context_and_unverified_data_disclaimer(self):
        result = analyze_food_claims(
            "Gluten Free",
            product(ingredients="Rice flour"),
            dietary_preferences=["gluten_free"],
            manual_input=True,
        )
        self.assertEqual(result["claims"][0]["status"], "unverifiable")
        self.assertEqual(len(result["personal_context"]), 1)
        self.assertIn("not independently verified", result["disclaimer"])

    def test_manual_unrecognized_claim_text_is_not_dropped(self):
        claims = detect_food_claims(
            "High protein, formulated for cellular renewal",
            include_manual_unknown=True,
        )
        self.assertEqual(
            [claim["code"] for claim in claims],
            ["high_protein", "unrecognized_claim"],
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
