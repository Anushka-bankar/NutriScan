import test from 'node:test';
import assert from 'node:assert/strict';
import { parseNutritionLabel } from '../src/utils/labelParser.js';

test('extracts identity, category, serving size, nutrition, and ingredient text', () => {
  const result = parseNutritionLabel(`Nutrition Information per 100 g
Product name: Rolled oats
Brand: Grain House
Serving size 30 g
Energy 1500 kJ 360 kcal
Carbohydrates 60 g
of which sugars 12 g
Protein 10 g
Fat 5 g
Saturated fat 1 g
Fibre 8 g
Salt 0.5 g
Ingredients: whole grain oats, raisins
Allergens: may contain nuts`);

  assert.equal(result.basis, '100g');
  assert.equal(result.name, 'Rolled oats');
  assert.equal(result.brand, 'Grain House');
  assert.equal(result.category, 'grains_cereals');
  assert.equal(result.nameConfidence, 'high');
  assert.equal(result.serving_size_g, '30');
  assert.equal(result.energy_kj, '1500');
  assert.equal(result.calories_kcal, '360');
  assert.equal(result.carbohydrates_g, '60');
  assert.equal(result.sugars_g, '12');
  assert.equal(result.sodium_mg, '200');
  assert.equal(result.ingredients, 'whole grain oats, raisins');
});

test('keeps absent values unavailable and detects per-serving labels', () => {
  const result = parseNutritionLabel(`Per serving
Serving size: 25 g
Protein 7.5 g
Ingredients: chickpeas, water`);

  assert.equal(result.basis, 'serving');
  assert.equal(result.serving_size_g, '25');
  assert.equal(result.protein_g, '7.5');
  assert.equal(result.calories_kcal, '');
  assert.equal(result.sodium_mg, '');
  assert.ok(result.uncertainFields.includes('brand'));
  assert.ok(result.uncertainFields.includes('calories_kcal'));
  assert.ok(result.warnings.some((warning) => warning.includes('not detected')));
});

test('leaves serving amounts as read for one explicit conversion in review flow', () => {
  const result = parseNutritionLabel(`Nutrition per serving
Product name: Protein snack
Serving size 25 g
Energy 100 kcal
Protein 5 g
Salt 0.2 g`);

  assert.equal(result.basis, 'serving');
  assert.equal(result.calories_kcal, '100');
  assert.equal(result.protein_g, '5');
  assert.equal(result.sodium_mg, '80');
  assert.equal(result.category, 'snacks');
});

test('marks mixed bases and low OCR confidence for review', () => {
  const result = parseNutritionLabel(`Nutrition facts per 100 g and per serving
Product name: Breakfast cereal
Energy 400 kcal
Carbohydrates 70 g`, { confidence: 42 });

  assert.ok(result.uncertainFields.includes('basis'));
  assert.ok(result.uncertainFields.includes('energy_kj'));
  assert.ok(result.warnings.some((warning) => warning.includes('OCR confidence is low')));
});

test('auto-populates a product name but marks an unlabeled header uncertain', () => {
  const result = parseNutritionLabel(`Green Valley Oat Bites
Nutrition Facts per 100 g
Energy 390 kcal
Protein 8 g
Ingredients: oats, honey`);

  assert.equal(result.name, 'Green Valley Oat Bites');
  assert.equal(result.brand, '');
  assert.equal(result.nameConfidence, 'low');
  assert.equal(result.category, 'grains_cereals');
  assert.ok(result.uncertainFields.includes('name'));
  assert.ok(result.uncertainFields.includes('category'));
});

test('flags a suspicious serving size rather than silently accepting it', () => {
  const result = parseNutritionLabel(`Nutrition per serving
Product name: Protein bar
Serving size 0.5 g
Energy 180 kcal
Protein 12 g`);

  assert.equal(result.serving_size_g, '0.5');
  assert.equal(result.calories_kcal, '');
  assert.ok(result.uncertainFields.includes('serving_size_g'));
  assert.ok(result.warnings.some((warning) => warning.includes('Serving size looks unusual')));
});

test('extracts a cocoa powder pack when the nutrient unit is implicit in the panel heading', () => {
  const result = parseNutritionLabel(`COCO POWDER
JAYJEET
Ingredients :
Cocoa Solids 99.75%
Nature Identical Flavouring
Substance - Chocolate.
Use :
Chocolate Cakes, Brownies, Cookies
Nutritional Fact as Per 100g
Calories 393 Kcal
Saturated fat 7.1 g.
Fat 11.1 g
of Which Sugar 0
Carbohydrate 49.7 g.
Salt 0.1 g
Protein 23.3 g.
Packed & Marketed By :
JAYJEET FOOD`);

  assert.equal(result.name, 'COCO POWDER');
  assert.equal(result.brand, 'JAYJEET FOOD');
  assert.equal(result.category, 'other');
  assert.ok(result.uncertainFields.includes('category'));
  assert.equal(result.ingredients, 'Cocoa Solids 99.75% Nature Identical Flavouring Substance - Chocolate.');
  assert.equal(result.calories_kcal, '393');
  assert.equal(result.saturated_fat_g, '7.1');
  assert.equal(result.total_fat_g, '11.1');
  assert.equal(result.sugars_g, '0');
  assert.equal(result.carbohydrates_g, '49.7');
  assert.equal(result.sodium_mg, '40');
  assert.equal(result.protein_g, '23.3');
  assert.ok(result.uncertainFields.includes('brand'));
  assert.ok(result.uncertainFields.includes('sugars_g'));
});

test('does not silently populate suspicious nutrient values', () => {
  const result = parseNutritionLabel(`Nutrition information per 100 g
Product name: Snack food
Energy 9000 kcal
Carbohydrates 110 g
Protein 4 g`);

  assert.equal(result.calories_kcal, '');
  assert.equal(result.carbohydrates_g, '');
  assert.ok(result.uncertainFields.includes('calories_kcal'));
  assert.ok(result.uncertainFields.includes('carbohydrates_g'));
});
