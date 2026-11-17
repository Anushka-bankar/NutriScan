import unittest
from types import SimpleNamespace

from app.ingredient_analyzer import analyze_ingredient_list, split_ingredients


class IngredientAnalyzerTests(unittest.TestCase):
    def test_splits_nested_ingredients_without_splitting_parenthetical_commas(self):
        self.assertEqual(
            split_ingredients("Chocolate (sugar, cocoa), salt; water"),
            ["Chocolate", "sugar", "cocoa", "salt", "water"],
        )

    def test_classifies_known_items_and_preserves_unknown_information(self):
        result = analyze_ingredient_list(
            "Sugar, sodium benzoate, E322, Yellow 5, mystery extract"
        )
        entries = {entry["name"]: entry for entry in result["entries"]}
        self.assertEqual(entries["Sugar"]["category"], "sweetener")
        self.assertEqual(entries["sodium benzoate"]["category"], "preservative")
        self.assertEqual(entries["E322"]["category"], "emulsifier")
        self.assertEqual(entries["Yellow 5"]["category"], "colouring_agent")
        self.assertEqual(entries["mystery extract"]["category"], "unclassified")
        self.assertEqual(
            entries["mystery extract"]["evidence_status"],
            "insufficient_information",
        )
        self.assertIn("cannot be reliably determined", entries["mystery extract"]["common_purpose"])

    def test_personalizes_dietary_notes_without_overstating_health_effects(self):
        profile = SimpleNamespace(
            dietary_preferences=["vegan", "dairy_free", "gluten_free"],
            health_goal="manage_condition",
        )
        result = analyze_ingredient_list(
            "Soy lecithin, milk powder, wheat flour, may contain egg, unknown",
            profile,
        )
        entries = {entry["name"]: entry for entry in result["entries"]}
        self.assertIn("soybeans", entries["Soy lecithin"]["health_considerations"])
        milk_statuses = {
            item["status"]
            for item in entries["milk powder"]["dietary_considerations"]
        }
        self.assertEqual(milk_statuses, {"conflict"})
        egg_statuses = {
            item["status"]
            for item in entries["may contain egg"]["dietary_considerations"]
        }
        self.assertEqual(egg_statuses, {"verify"})
        self.assertIn("condition-management goal", result["summary"]["health_goal_context"])
        self.assertEqual(result["summary"]["unmatched_count"], 1)

    def test_plant_milk_is_not_misclassified_as_dairy(self):
        result = analyze_ingredient_list(
            "Coconut milk, oat milk, almond milk, soy milk",
            SimpleNamespace(dietary_preferences=["dairy_free"], health_goal=None),
        )
        self.assertTrue(
            all(
                not entry["dietary_considerations"]
                for entry in result["entries"]
            )
        )
        self.assertIn(
            "The FDA identifies soybeans as a U.S. major food allergen",
            result["entries"][-1]["health_considerations"],
        )

    def test_ambiguous_flavour_descriptors_are_not_claimed_as_animal_ingredients(self):
        result = analyze_ingredient_list("Plant-based chicken flavour")
        self.assertEqual(result["entries"][0]["category"], "unclassified")

    def test_rejects_empty_non_text_oversized_and_too_many_items(self):
        for invalid in ("", "  ", None, 42):
            with self.subTest(value=invalid):
                with self.assertRaises(ValueError):
                    split_ingredients(invalid)
        with self.assertRaises(ValueError):
            split_ingredients("x" * 10001)
        with self.assertRaises(ValueError):
            split_ingredients(", ".join(["sugar"] * 101))
        with self.assertRaises(ValueError):
            split_ingredients("(" * 22 + "sugar" + ")" * 22)


if __name__ == "__main__":
    unittest.main(verbosity=2)
