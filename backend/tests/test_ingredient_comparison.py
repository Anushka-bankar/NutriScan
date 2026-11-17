import unittest

from app.ingredient_comparison import (
    compare_ingredient_snapshots,
    normalize_ingredient_name,
)


class IngredientComparisonTests(unittest.TestCase):
    def test_normalizes_case_spacing_punctuation_accents_and_additive_codes(self):
        self.assertEqual(
            normalize_ingredient_name("  Crème  fraîche! "),
            normalize_ingredient_name("creme-fraiche"),
        )
        self.assertEqual(normalize_ingredient_name("E-322"), "e322")
        self.assertEqual(normalize_ingredient_name("E 322"), "e322")

    def test_identifies_added_removed_and_unchanged_ingredients(self):
        result = compare_ingredient_snapshots(
            {
                "entries": [
                    {"name": "Cane sugar", "category": "sweetener"},
                    {"name": "Salt", "category": "general_food_ingredient"},
                    {"name": "Corn starch", "category": "unclassified"},
                ]
            },
            {
                "entries": [
                    {"name": " cane-sugar ", "category": "sweetener"},
                    {"name": "Salt", "category": "general_food_ingredient"},
                    {"name": "Glucose", "category": "sweetener"},
                ]
            },
        )

        self.assertEqual([item["name"] for item in result["added"]], ["Glucose"])
        self.assertEqual(
            [item["name"] for item in result["removed"]], ["Corn starch"]
        )
        self.assertEqual(
            [item["name"] for item in result["unchanged"]],
            [" cane-sugar ", "Salt"],
        )
        self.assertFalse(result["classification_changes"])
        self.assertFalse(result["explanation_changes"])

    def test_detects_reordering_without_treating_it_as_addition_or_removal(self):
        result = compare_ingredient_snapshots(
            {"entries": [{"name": "Oats"}, {"name": "Salt"}, {"name": "Sugar"}]},
            {"entries": [{"name": "Salt"}, {"name": "Oats"}, {"name": "Sugar"}]},
        )

        self.assertEqual(result["added"], [])
        self.assertEqual(result["removed"], [])
        self.assertEqual(len(result["unchanged"]), 3)
        self.assertEqual(len(result["order_changes"]), 1)

    def test_reports_saved_classification_and_explanation_changes(self):
        result = compare_ingredient_snapshots(
            {
                "entries": [
                    {
                        "name": "Lecithin",
                        "category": "general_food_ingredient",
                        "what_it_is": "Older description",
                        "common_purpose": "Helps ingredients mix.",
                        "evidence_status": "insufficient_information",
                    }
                ]
            },
            {
                "entries": [
                    {
                        "name": "lecithin",
                        "category": "emulsifier",
                        "what_it_is": "Updated description",
                        "common_purpose": "Helps ingredients mix.",
                        "evidence_status": "purpose_reference_only",
                    }
                ]
            },
        )

        self.assertEqual(result["classification_changes"][0]["changes"][0]["field"], "category")
        self.assertEqual(
            result["explanation_changes"][0]["changes"][0]["field"],
            "what_it_is",
        )
        self.assertEqual(len(result["explanation_changes"][0]["changes"]), 2)

    def test_duplicate_occurrences_are_compared_by_count(self):
        result = compare_ingredient_snapshots(
            {"entries": [{"name": "Salt"}, {"name": "Salt"}]},
            {"entries": [{"name": "salt"}]},
        )

        self.assertEqual(len(result["unchanged"]), 1)
        self.assertEqual(len(result["removed"]), 1)
        self.assertEqual(result["added"], [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
