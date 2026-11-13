import test from 'node:test';
import assert from 'node:assert/strict';
import { parseNutritionLabel } from '../src/utils/labelParser.js';

test('extracts labelled nutrition, serving size, and ingredient text', () => {
  const result = parseNutritionLabel(`Nutrition Information per 100 g
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
});
